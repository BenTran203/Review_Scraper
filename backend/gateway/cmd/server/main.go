package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/gin-gonic/gin"
	"reviewpulse/gateway/internal/api"
	"reviewpulse/gateway/internal/config"
	"reviewpulse/gateway/internal/models"
	"reviewpulse/gateway/internal/services"
)

func main() {
	cfg := config.Load()

	// --- Redis ---
	redisSvc, err := services.NewRedisClient(cfg.RedisURL, cfg.RedisPassword, cfg.SessionTTLHrs)
	if err != nil {
		log.Fatalf("Failed to connect to Redis: %v", err)
	}
	defer redisSvc.Close()
	log.Println("Connected to Redis")

	// --- RabbitMQ ---
	queueSvc, err := services.NewQueueService(cfg.RabbitMQURL)
	if err != nil {
		log.Fatalf("Failed to connect to RabbitMQ: %v", err)
	}
	defer queueSvc.Close()
	log.Println("Connected to RabbitMQ")

	// --- Services ---
	sessionSvc := services.NewSessionService(redisSvc)
	openaiSvc := services.NewOpenAIService(cfg.OpenAIKey)

	// --- Background worker: consume scrape results ---
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	results, err := queueSvc.ConsumeScrapeResults(ctx)
	if err != nil {
		log.Fatalf("Failed to start scrape result consumer: %v", err)
	}

	go processScrapeResults(ctx, results, sessionSvc, openaiSvc)

	// --- HTTP Server ---
	gin.SetMode(cfg.GinMode)
	router := gin.Default()
	api.SetupRoutes(router, sessionSvc, queueSvc, openaiSvc, redisSvc)

	go func() {
		addr := ":" + cfg.Port
		log.Printf("Gateway listening on %s", addr)
		if err := router.Run(addr); err != nil {
			log.Fatalf("Server failed: %v", err)
		}
	}()

	// --- Graceful shutdown ---
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down...")
	cancel()
}

// processScrapeResults listens for completed scrape jobs, runs OpenAI analysis,
// and stores the results in Redis.
func processScrapeResults(
	ctx context.Context,
	results <-chan models.ScrapeResult,
	sessions *services.SessionService,
	openai *services.OpenAIService,
) {
	for {
		select {
		case <-ctx.Done():
			return
		case result, ok := <-results:
			if !ok {
				return
			}
			handleScrapeResult(ctx, result, sessions, openai)
		}
	}
}

func handleScrapeResult(
	ctx context.Context,
	result models.ScrapeResult,
	sessions *services.SessionService,
	openai *services.OpenAIService,
) {
	token := result.Token

	if result.Error != "" {
		log.Printf("[worker] scrape error for %s: %s", token, result.Error)
		sessions.SetError(ctx, token, "Scraping failed: "+result.Error)
		return
	}

	if len(result.Reviews) == 0 {
		sessions.SetError(ctx, token, "No reviews found for this product")
		return
	}

	// Store reviews
	if err := sessions.StoreReviews(ctx, token, result.Reviews); err != nil {
		log.Printf("[worker] store reviews error for %s: %v", token, err)
		sessions.SetError(ctx, token, "Failed to store reviews")
		return
	}

	// Update status to analyzing
	if err := sessions.UpdateStatus(ctx, token, "analyzing"); err != nil {
		log.Printf("[worker] update status error for %s: %v", token, err)
	}

	// Get session for language preference
	session, err := sessions.Get(ctx, token)
	if err != nil {
		log.Printf("[worker] get session error for %s: %v", token, err)
		sessions.SetError(ctx, token, "Session expired during analysis")
		return
	}

	// Run OpenAI analysis
	analysis, err := openai.AnalyzeReviews(ctx, result.Reviews, session.OutputLanguage)
	if err != nil {
		log.Printf("[worker] openai error for %s: %v", token, err)
		sessions.SetError(ctx, token, "AI analysis failed")
		return
	}

	// Store results
	if err := sessions.StoreAnalysis(ctx, token, analysis); err != nil {
		log.Printf("[worker] store analysis error for %s: %v", token, err)
		sessions.SetError(ctx, token, "Failed to store analysis")
		return
	}

	// Mark complete
	if err := sessions.UpdateStatus(ctx, token, "complete"); err != nil {
		log.Printf("[worker] complete status error for %s: %v", token, err)
	}

	log.Printf("[worker] analysis complete for session %s (%d reviews, lang=%s)",
		token, len(result.Reviews), session.OutputLanguage)
}
