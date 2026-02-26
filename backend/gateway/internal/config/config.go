package config

import (
	"fmt"
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

type Config struct {
	Port          string
	GinMode       string
	RedisURL      string
	RedisPassword string
	RabbitMQURL    string
	AnthropicKey   string
	SessionTTLHrs  int
	MaxReviews    int
}

func Load() (*Config, error) {
	// Load .env
	_ = godotenv.Load()

	apiKey := os.Getenv("ANTHROPIC_API_KEY")
	if apiKey == "" {
		return nil, fmt.Errorf("ANTHROPIC_API_KEY is not set in .env file")
	}

	ttl, _ := strconv.Atoi(getEnv("SESSION_TTL_HOURS", "1"))
	maxReviews, _ := strconv.Atoi(getEnv("MAX_REVIEWS", "200"))

	return &Config{
		Port:          getEnv("PORT", "8080"),
		GinMode:       getEnv("GIN_MODE", "release"),
		RedisURL:      getEnv("REDIS_URL", "redis://localhost:6379"),
		RedisPassword: os.Getenv("REDIS_PASSWORD"),
		RabbitMQURL:   getEnv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
		AnthropicKey:  apiKey,
		SessionTTLHrs: ttl,
		MaxReviews:    maxReviews,
	}, nil
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
