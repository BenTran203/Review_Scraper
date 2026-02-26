package services

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"

	openai "github.com/sashabaranov/go-openai"
	"reviewpulse/gateway/internal/models"
)

// OpenAIService wraps the OpenAI API client.
// The API key is loaded from the environment and NEVER exposed in responses or logs.
type OpenAIService struct {
	client *openai.Client
}

// NewOpenAIService creates an OpenAI client. The key must be non-empty.
func NewOpenAIService(apiKey string) *OpenAIService {
	return &OpenAIService{
		client: openai.NewClient(apiKey),
	}
}

// AnalyzeReviews sends reviews to GPT-4o-mini and returns structured analysis.
func (o *OpenAIService) AnalyzeReviews(ctx context.Context, reviews []models.Review, language string) (*models.AnalysisResult, error) {
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

	resp, err := o.client.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
		Model: "gpt-4o-mini",
		Messages: []openai.ChatCompletionMessage{
			{Role: openai.ChatMessageRoleSystem, Content: systemPrompt},
			{Role: openai.ChatMessageRoleUser, Content: sb.String()},
		},
		Temperature: 0.3,
	})
	if err != nil {
		// IMPORTANT: Never log the API key. Only log the error message.
		log.Printf("[openai] API call failed: %v", err)
		return nil, fmt.Errorf("openai analysis failed: %w", err)
	}

	if len(resp.Choices) == 0 {
		return nil, fmt.Errorf("openai returned no choices")
	}

	raw := strings.TrimSpace(resp.Choices[0].Message.Content)
	// Strip markdown code fences if present
	raw = strings.TrimPrefix(raw, "```json")
	raw = strings.TrimPrefix(raw, "```")
	raw = strings.TrimSuffix(raw, "```")
	raw = strings.TrimSpace(raw)

	var result models.AnalysisResult
	if err := json.Unmarshal([]byte(raw), &result); err != nil {
		log.Printf("[openai] failed to parse response JSON: %v — raw: %s", err, raw)
		return nil, fmt.Errorf("failed to parse AI response: %w", err)
	}

	result.Language = language
	return &result, nil
}
