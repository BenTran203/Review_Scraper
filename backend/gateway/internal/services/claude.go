package services

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"

	"reviewpulse/gateway/internal/models"
)

const (
	claudeAPIURL     = "https://api.anthropic.com/v1/messages"
	claudeAPIVersion = "2023-06-01"
	claudeModel      = "claude-sonnet-4-20250514"
)

// ClaudeService wraps the Anthropic Claude API client.
// The API key is loaded from the environment and NEVER exposed in responses or logs.
type ClaudeService struct {
	apiKey string
	client *http.Client
}

// NewClaudeService creates a Claude client. The key must be non-empty.
func NewClaudeService(apiKey string) *ClaudeService {
	return &ClaudeService{
		apiKey: apiKey,
		client: &http.Client{},
	}
}

// claudeRequest is the request body for the Anthropic Messages API.
type claudeRequest struct {
	Model       string          `json:"model"`
	MaxTokens   int             `json:"max_tokens"`
	System      string          `json:"system"`
	Messages    []claudeMessage `json:"messages"`
	Temperature float64         `json:"temperature"`
}

// claudeMessage represents a single message in a Claude conversation.
type claudeMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// claudeResponse is the response from the Anthropic Messages API.
type claudeResponse struct {
	Content []struct {
		Type string `json:"type"`
		Text string `json:"text"`
	} `json:"content"`
	Error *struct {
		Type    string `json:"type"`
		Message string `json:"message"`
	} `json:"error"`
}

// AnalyzeReviews sends reviews to Claude and returns structured analysis.
func (c *ClaudeService) AnalyzeReviews(ctx context.Context, reviews []models.Review, language string) (*models.AnalysisResult, error) {
	langName, ok := models.SupportedLanguages[language]
	if !ok {
		langName = "English"
		language = "en"
	}

	// Build review text block
	var sb strings.Builder
	for i, r := range reviews {
		sb.WriteString(fmt.Sprintf("Review %d (Rating: %.1f/5): %s\n", i+1, r.Rating, r.Text))
	}

	systemPrompt := fmt.Sprintf(`You are a product review analyst. Respond ENTIRELY in %s.

Analyze the customer reviews provided and return a JSON object with exactly this structure:
{
  "summary": "A 2-3 sentence overall summary of customer opinions",
  "pros": ["pro 1", "pro 2", ...],
  "cons": ["con 1", "con 2", ...],
  "sentiment": {"positive": <count>, "neutral": <count>, "negative": <count>},
  "keywords": ["keyword1", "keyword2", ...]
}

Rules:
- List 3-8 pros and 3-8 cons, derived from actual review content.
- sentiment counts must add up to the total number of reviews.
- keywords: top 5-10 most frequently mentioned product aspects.
- Respond ONLY with valid JSON. No markdown, no explanation.`, langName)

	reqBody := claudeRequest{
		Model:       claudeModel,
		MaxTokens:   4096,
		System:      systemPrompt,
		Messages:    []claudeMessage{{Role: "user", Content: sb.String()}},
		Temperature: 0.3,
	}

	bodyBytes, err := json.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, claudeAPIURL, bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("x-api-key", c.apiKey)
	req.Header.Set("anthropic-version", claudeAPIVersion)

	resp, err := c.client.Do(req)
	if err != nil {
		// IMPORTANT: Never log the API key. Only log the error message.
		log.Printf("[claude] API call failed: %v", err)
		return nil, fmt.Errorf("claude analysis failed: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		log.Printf("[claude] API returned status %d: %s", resp.StatusCode, string(respBody))
		return nil, fmt.Errorf("claude API error (status %d)", resp.StatusCode)
	}

	var claudeResp claudeResponse
	if err := json.Unmarshal(respBody, &claudeResp); err != nil {
		log.Printf("[claude] failed to parse API response: %v", err)
		return nil, fmt.Errorf("failed to parse claude response: %w", err)
	}

	if claudeResp.Error != nil {
		return nil, fmt.Errorf("claude error: %s", claudeResp.Error.Message)
	}

	if len(claudeResp.Content) == 0 {
		return nil, fmt.Errorf("claude returned no content")
	}

	// Extract text from the first content block
	raw := ""
	for _, block := range claudeResp.Content {
		if block.Type == "text" {
			raw = strings.TrimSpace(block.Text)
			break
		}
	}
	if raw == "" {
		return nil, fmt.Errorf("claude returned no text content")
	}

	// Strip markdown code fences if present
	raw = strings.TrimPrefix(raw, "```json")
	raw = strings.TrimPrefix(raw, "```")
	raw = strings.TrimSuffix(raw, "```")
	raw = strings.TrimSpace(raw)

	var result models.AnalysisResult
	if err := json.Unmarshal([]byte(raw), &result); err != nil {
		log.Printf("[claude] failed to parse response JSON: %v — raw: %s", err, raw)
		return nil, fmt.Errorf("failed to parse AI response: %w", err)
	}

	result.Language = language
	return &result, nil
}
