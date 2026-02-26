package middleware

import (
	"fmt"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"reviewpulse/gateway/internal/services"
)

// RateLimit returns a middleware that limits requests per IP using Redis.
// maxRequests is the maximum number of requests allowed within windowSecs.
func RateLimit(redis *services.RedisClient, maxRequests int64, windowSecs int) gin.HandlerFunc {
	window := time.Duration(windowSecs) * time.Second

	return func(c *gin.Context) {
		ip := c.ClientIP()
		key := fmt.Sprintf("ratelimit:%s", ip)

		count, err := redis.Incr(c.Request.Context(), key, window)
		if err != nil {
			// If Redis is down, allow the request but log the error.
			c.Next()
			return
		}

		if count > maxRequests {
			c.JSON(http.StatusTooManyRequests, gin.H{
				"error": "rate limit exceeded, please try again later",
			})
			c.Abort()
			return
		}

		c.Next()
	}
}
