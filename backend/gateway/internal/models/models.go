package models

import "time"

// Session represents an active user analysis session stored in Redis.
type Session struct {
	Token          string    `json:"token"`
	URL            string    `json:"url"`
	Platform       string    `json:"platform"`
	Status         string    `json:"status"` // pending | scraping | analyzing | complete | error
	OutputLanguage string    `json:"output_language"`
	ErrorMessage   string    `json:"error_message,omitempty"`
	CreatedAt      time.Time `json:"created_at"`
}

// Review is a single scraped customer review.
type Review struct {
	Text   string  `json:"text"`
	Rating float64 `json:"rating"`
	Date   string  `json:"date"`
}

// AnalysisResult holds the AI-generated output.
type AnalysisResult struct {
	Summary   string        `json:"summary"`
	Pros      []string      `json:"pros"`
	Cons      []string      `json:"cons"`
	Sentiment SentimentData `json:"sentiment"`
	Keywords  []string      `json:"keywords"`
	Language  string        `json:"language"`
}

// SentimentData holds counts per sentiment category.
type SentimentData struct {
	Positive int `json:"positive"`
	Neutral  int `json:"neutral"`
	Negative int `json:"negative"`
}

// AnalyzeRequest is the JSON body for POST /api/analyze.
type AnalyzeRequest struct {
	URL            string `json:"url" binding:"required"`
	OutputLanguage string `json:"output_language"` // en | vi | es | ja
	SessionToken   string `json:"session_token"`
}

// ScrapeJob is published to RabbitMQ for the Python worker.
type ScrapeJob struct {
	Token    string `json:"token"`
	URL      string `json:"url"`
	Platform string `json:"platform"`
}

// ScrapeResult is received from the Python worker via RabbitMQ.
type ScrapeResult struct {
	Token   string   `json:"token"`
	Reviews []Review `json:"reviews"`
	Error   string   `json:"error,omitempty"`
}

// ProgressEvent is sent over SSE to the frontend.
type ProgressEvent struct {
	Status  string `json:"status"`
	Message string `json:"message,omitempty"`
}

// SupportedLanguages maps language codes to full names for OpenAI prompts.
var SupportedLanguages = map[string]string{
	"en": "English",
	"vi": "Vietnamese",
	"es": "Spanish",
	"ja": "Japanese",
}

// SupportedPlatforms maps URL patterns to platform names.
var SupportedPlatforms = map[string]string{
	"amazon":  "amazon",
	"shopee":  "shopee",
	"ebay":    "ebay",
	"lazada":  "lazada",
	"tiki":    "tiki",
}
