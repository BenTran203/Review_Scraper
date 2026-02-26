package api

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"reviewpulse/gateway/internal/models"
)

// StreamProgress sends Server-Sent Events with session status updates.
// The client connects and receives events until the session reaches a
// terminal state (complete or error) or the connection is closed.
func (h *Handler) StreamProgress(c *gin.Context) {
	token := c.Param("token")
	ctx := c.Request.Context()

	// Verify session exists
	exists, err := h.sessions.Exists(ctx, token)
	if err != nil || !exists {
		c.JSON(http.StatusNotFound, gin.H{"error": "session not found"})
		return
	}

	// Set SSE headers
	c.Writer.Header().Set("Content-Type", "text/event-stream")
	c.Writer.Header().Set("Cache-Control", "no-cache")
	c.Writer.Header().Set("Connection", "keep-alive")
	c.Writer.Header().Set("Access-Control-Allow-Origin", "*")
	c.Writer.Flush()

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	lastStatus := ""

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			session, err := h.sessions.Get(ctx, token)
			if err != nil {
				sendSSE(c, "error", &models.ProgressEvent{
					Status:  "error",
					Message: "session expired or not found",
				})
				return
			}

			// Only send an event when the status changes.
			if session.Status == lastStatus {
				// Send a heartbeat comment to keep the connection alive.
				fmt.Fprintf(c.Writer, ": heartbeat\n\n")
				c.Writer.Flush()
				continue
			}
			lastStatus = session.Status

			event := &models.ProgressEvent{
				Status:  session.Status,
				Message: statusMessage(session),
			}

			sendSSE(c, "status", event)

			// Terminal states — close the stream.
			if session.Status == "complete" || session.Status == "error" {
				return
			}
		}
	}
}

// sendSSE writes a single SSE event.
func sendSSE(c *gin.Context, eventName string, data interface{}) {
	jsonData, err := json.Marshal(data)
	if err != nil {
		log.Printf("[sse] marshal error: %v", err)
		return
	}
	fmt.Fprintf(c.Writer, "event: %s\n", eventName)
	fmt.Fprintf(c.Writer, "data: %s\n\n", jsonData)
	c.Writer.Flush()
}

// statusMessage returns a human-readable message for the current session state.
func statusMessage(s *models.Session) string {
	switch s.Status {
	case "pending":
		return "Waiting to start..."
	case "scraping":
		return "Scraping reviews from " + s.Platform + "..."
	case "analyzing":
		return "Analyzing reviews with AI..."
	case "complete":
		return "Analysis complete!"
	case "error":
		if s.ErrorMessage != "" {
			return s.ErrorMessage
		}
		return "An error occurred."
	default:
		return s.Status
	}
}
