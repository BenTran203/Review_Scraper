package api

import (
	"log"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"reviewpulse/gateway/internal/models"
	"reviewpulse/gateway/internal/services"
)

// Handler holds dependencies for HTTP handlers.
type Handler struct {
	sessions *services.SessionService
	queue    *services.QueueService
	openai   *services.OpenAIService
}

// NewHandler creates a Handler with all required services.
func NewHandler(
	sessions *services.SessionService,
	queue *services.QueueService,
	openai *services.OpenAIService,
) *Handler {
	return &Handler{sessions: sessions, queue: queue, openai: openai}
}

// HealthCheck returns 200 if the gateway and its dependencies are healthy.
func (h *Handler) HealthCheck(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"status":   "ok",
		"service":  "reviewpulse-gateway",
	})
}

// CreateSession creates a new empty session and returns the token.
func (h *Handler) CreateSession(c *gin.Context) {
	session, err := h.sessions.Create(c.Request.Context(), "", "", "en")
	if err != nil {
		log.Printf("[handler] create session error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create session"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"token": session.Token})
}

// Heartbeat refreshes the TTL for a session.
func (h *Handler) Heartbeat(c *gin.Context) {
	token := c.Param("token")
	if token == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing token"})
		return
	}

	exists, err := h.sessions.Exists(c.Request.Context(), token)
	if err != nil || !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": "session not found"})
		return
	}

	if err := h.sessions.Heartbeat(c.Request.Context(), token); err != nil {
		log.Printf("[handler] heartbeat error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "heartbeat failed"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}

// GetSession returns session metadata and analysis results if available.
func (h *Handler) GetSession(c *gin.Context) {
	token := c.Param("token")
	ctx := c.Request.Context()

	session, err := h.sessions.Get(ctx, token)
	if err != nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "session not found"})
		return
	}

	resp := gin.H{
		"session": session,
	}

	// Include analysis if complete.
	if session.Status == "complete" {
		analysis, err := h.sessions.GetAnalysis(ctx, token)
		if err == nil {
			resp["analysis"] = analysis
		}
	}

	c.JSON(http.StatusOK, resp)
}

// Analyze validates the URL, creates a session, and enqueues a scrape job.
func (h *Handler) Analyze(c *gin.Context) {
	var req models.AnalyzeRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "url is required"})
		return
	}

	// Validate output language
	lang := req.OutputLanguage
	if lang == "" {
		lang = "en"
	}
	if _, ok := models.SupportedLanguages[lang]; !ok {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":               "unsupported language",
			"supported_languages": models.SupportedLanguages,
		})
		return
	}

	// Detect platform from URL
	platform := detectPlatform(req.URL)
	if platform == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":               "unsupported platform",
			"supported_platforms": []string{"amazon", "shopee", "ebay", "lazada", "tiki"},
		})
		return
	}

	ctx := c.Request.Context()

	// Create session
	session, err := h.sessions.Create(ctx, req.URL, platform, lang)
	if err != nil {
		log.Printf("[handler] create session: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create session"})
		return
	}

	// Update status to scraping
	if err := h.sessions.UpdateStatus(ctx, session.Token, "scraping"); err != nil {
		log.Printf("[handler] update status: %v", err)
	}

	// Publish scrape job
	job := &models.ScrapeJob{
		Token:    session.Token,
		URL:      req.URL,
		Platform: platform,
	}
	if err := h.queue.PublishScrapeJob(ctx, job); err != nil {
		log.Printf("[handler] publish scrape job: %v", err)
		h.sessions.SetError(ctx, session.Token, "failed to enqueue scraping job")
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to start analysis"})
		return
	}

	c.JSON(http.StatusAccepted, gin.H{
		"token":    session.Token,
		"status":   "scraping",
		"platform": platform,
		"language": lang,
	})
}

// detectPlatform identifies the e-commerce platform from a URL.
func detectPlatform(url string) string {
	lower := strings.ToLower(url)
	for keyword, platform := range models.SupportedPlatforms {
		if strings.Contains(lower, keyword) {
			return platform
		}
	}
	return ""
}
