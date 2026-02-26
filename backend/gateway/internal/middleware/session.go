package middleware

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"reviewpulse/gateway/internal/services"
)

// ValidateSession is a middleware that checks the X-Session-Token header
// and verifies the session exists in Redis.
func ValidateSession(sessions *services.SessionService) gin.HandlerFunc {
	return func(c *gin.Context) {
		token := c.GetHeader("X-Session-Token")
		if token == "" {
			token = c.Query("token")
		}
		if token == "" {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "session token required"})
			c.Abort()
			return
		}

		exists, err := sessions.Exists(c.Request.Context(), token)
		if err != nil || !exists {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid or expired session"})
			c.Abort()
			return
		}

		c.Set("session_token", token)
		c.Next()
	}
}
