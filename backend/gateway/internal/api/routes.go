package api

import (
	"github.com/gin-gonic/gin"
	"reviewpulse/gateway/internal/middleware"
	"reviewpulse/gateway/internal/services"
)

// SetupRoutes registers all HTTP routes on the Gin engine.
func SetupRoutes(
	r *gin.Engine,
	sessions *services.SessionService,
	queue *services.QueueService,
	openaiSvc *services.OpenAIService,
	redisSvc *services.RedisClient,
) {
	handler := NewHandler(sessions, queue, openaiSvc)

	r.Use(middleware.CORS())

	api := r.Group("/api")
	api.Use(middleware.RateLimit(redisSvc, 30, 60)) // 30 requests per 60 seconds per IP

	api.GET("/health", handler.HealthCheck)
	api.POST("/session", handler.CreateSession)
	api.POST("/session/:token/heartbeat", handler.Heartbeat)
	api.GET("/session/:token", handler.GetSession)
	api.POST("/analyze", handler.Analyze)
	api.GET("/analyze/:token/stream", handler.StreamProgress)
}
