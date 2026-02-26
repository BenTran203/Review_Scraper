package services

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

// RedisClient wraps the go-redis client with helper methods.
type RedisClient struct {
	client *redis.Client
	ttl    time.Duration
}

// NewRedisClient creates a connected Redis client.
func NewRedisClient(redisURL string, password string, ttlHours int) (*RedisClient, error) {
	var opts *redis.Options

	if redisURL != "" {
		var err error
		opts, err = redis.ParseURL(redisURL)
		if err != nil {
			return nil, fmt.Errorf("invalid redis URL: %w", err)
		}
	} else {
		opts = &redis.Options{
			Addr:     "localhost:6379",
			Password: password,
			DB:       0,
		}
	}

	client := redis.NewClient(opts)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("redis ping failed: %w", err)
	}

	return &RedisClient{
		client: client,
		ttl:    time.Duration(ttlHours) * time.Hour,
	}, nil
}

// SetJSON stores a value as JSON with the session TTL.
func (r *RedisClient) SetJSON(ctx context.Context, key string, value interface{}) error {
	data, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("marshal error: %w", err)
	}
	return r.client.Set(ctx, key, data, r.ttl).Err()
}

// GetJSON retrieves a JSON value and unmarshals it into dest.
func (r *RedisClient) GetJSON(ctx context.Context, key string, dest interface{}) error {
	data, err := r.client.Get(ctx, key).Bytes()
	if err != nil {
		return err
	}
	return json.Unmarshal(data, dest)
}

// RefreshTTL resets the TTL on all keys matching a prefix.
func (r *RedisClient) RefreshTTL(ctx context.Context, prefix string) error {
	keys, err := r.client.Keys(ctx, prefix+"*").Result()
	if err != nil {
		return err
	}
	pipe := r.client.Pipeline()
	for _, key := range keys {
		pipe.Expire(ctx, key, r.ttl)
	}
	_, err = pipe.Exec(ctx)
	return err
}

// Delete removes a key.
func (r *RedisClient) Delete(ctx context.Context, key string) error {
	return r.client.Del(ctx, key).Err()
}

// Exists checks whether a key exists.
func (r *RedisClient) Exists(ctx context.Context, key string) (bool, error) {
	n, err := r.client.Exists(ctx, key).Result()
	return n > 0, err
}

// Ping checks Redis connectivity.
func (r *RedisClient) Ping(ctx context.Context) error {
	return r.client.Ping(ctx).Err()
}

// Close shuts down the Redis client.
func (r *RedisClient) Close() error {
	return r.client.Close()
}

// Incr increments a key (for rate limiting).
func (r *RedisClient) Incr(ctx context.Context, key string, expiry time.Duration) (int64, error) {
	count, err := r.client.Incr(ctx, key).Result()
	if err != nil {
		return 0, err
	}
	// Set expiry only on the first increment so the window is fixed
	if count == 1 {
		r.client.Expire(ctx, key, expiry)
	}
	return count, nil
}
