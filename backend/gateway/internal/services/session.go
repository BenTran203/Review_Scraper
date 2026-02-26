package services

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"reviewpulse/gateway/internal/models"
)

// SessionService manages user analysis sessions in Redis.
type SessionService struct {
	redis *RedisClient
}

// NewSessionService creates a new SessionService.
func NewSessionService(redis *RedisClient) *SessionService {
	return &SessionService{redis: redis}
}

func sessionKey(token, suffix string) string {
	return fmt.Sprintf("session:%s:%s", token, suffix)
}

// Create initialises a new session and returns its token.
func (s *SessionService) Create(ctx context.Context, url, platform, lang string) (*models.Session, error) {
	token := uuid.New().String()

	session := &models.Session{
		Token:          token,
		URL:            url,
		Platform:       platform,
		Status:         "pending",
		OutputLanguage: lang,
		CreatedAt:      time.Now().UTC(),
	}

	if err := s.redis.SetJSON(ctx, sessionKey(token, "meta"), session); err != nil {
		return nil, fmt.Errorf("create session: %w", err)
	}
	return session, nil
}

// Get retrieves session metadata.
func (s *SessionService) Get(ctx context.Context, token string) (*models.Session, error) {
	var session models.Session
	if err := s.redis.GetJSON(ctx, sessionKey(token, "meta"), &session); err != nil {
		return nil, err
	}
	return &session, nil
}

// UpdateStatus changes the session status.
func (s *SessionService) UpdateStatus(ctx context.Context, token, status string) error {
	session, err := s.Get(ctx, token)
	if err != nil {
		return err
	}
	session.Status = status
	return s.redis.SetJSON(ctx, sessionKey(token, "meta"), session)
}

// SetError marks the session as errored with a message.
func (s *SessionService) SetError(ctx context.Context, token, msg string) error {
	session, err := s.Get(ctx, token)
	if err != nil {
		return err
	}
	session.Status = "error"
	session.ErrorMessage = msg
	return s.redis.SetJSON(ctx, sessionKey(token, "meta"), session)
}

// Heartbeat refreshes the TTL on all keys for a session.
func (s *SessionService) Heartbeat(ctx context.Context, token string) error {
	return s.redis.RefreshTTL(ctx, fmt.Sprintf("session:%s:", token))
}

// StoreReviews saves scraped reviews.
func (s *SessionService) StoreReviews(ctx context.Context, token string, reviews []models.Review) error {
	return s.redis.SetJSON(ctx, sessionKey(token, "reviews"), reviews)
}

// GetReviews retrieves scraped reviews.
func (s *SessionService) GetReviews(ctx context.Context, token string) ([]models.Review, error) {
	var reviews []models.Review
	err := s.redis.GetJSON(ctx, sessionKey(token, "reviews"), &reviews)
	return reviews, err
}

// StoreAnalysis saves AI analysis results.
func (s *SessionService) StoreAnalysis(ctx context.Context, token string, result *models.AnalysisResult) error {
	return s.redis.SetJSON(ctx, sessionKey(token, "analysis"), result)
}

// GetAnalysis retrieves AI analysis results.
func (s *SessionService) GetAnalysis(ctx context.Context, token string) (*models.AnalysisResult, error) {
	var result models.AnalysisResult
	err := s.redis.GetJSON(ctx, sessionKey(token, "analysis"), &result)
	if err != nil {
		return nil, err
	}
	return &result, nil
}

// Exists checks whether a session token is valid.
func (s *SessionService) Exists(ctx context.Context, token string) (bool, error) {
	return s.redis.Exists(ctx, sessionKey(token, "meta"))
}
