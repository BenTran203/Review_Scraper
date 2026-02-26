package services

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	amqp "github.com/rabbitmq/amqp091-go"
	"reviewpulse/gateway/internal/models"
)

const (
	ScrapeJobsQueue   = "scrape_jobs"
	ScrapeResultQueue = "scrape_results"
)

// QueueService manages RabbitMQ connections and publishing/consuming.
type QueueService struct {
	conn    *amqp.Connection
	channel *amqp.Channel
}

// NewQueueService connects to RabbitMQ and declares the required queues.
func NewQueueService(url string) (*QueueService, error) {
	conn, err := amqp.Dial(url)
	if err != nil {
		return nil, fmt.Errorf("rabbitmq dial: %w", err)
	}

	ch, err := conn.Channel()
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("rabbitmq channel: %w", err)
	}

	// Declare queues (idempotent).
	for _, name := range []string{ScrapeJobsQueue, ScrapeResultQueue} {
		if _, err := ch.QueueDeclare(name, true, false, false, false, nil); err != nil {
			ch.Close()
			conn.Close()
			return nil, fmt.Errorf("declare queue %s: %w", name, err)
		}
	}

	return &QueueService{conn: conn, channel: ch}, nil
}

// PublishScrapeJob sends a scraping job for the Python worker.
func (q *QueueService) PublishScrapeJob(ctx context.Context, job *models.ScrapeJob) error {
	body, err := json.Marshal(job)
	if err != nil {
		return err
	}

	return q.channel.PublishWithContext(ctx, "", ScrapeJobsQueue, false, false, amqp.Publishing{
		ContentType:  "application/json",
		Body:         body,
		DeliveryMode: amqp.Persistent,
		Timestamp:    time.Now(),
	})
}

// ConsumeScrapeResults returns a channel of ScrapeResult messages.
// It runs until the context is cancelled.
func (q *QueueService) ConsumeScrapeResults(ctx context.Context) (<-chan models.ScrapeResult, error) {
	msgs, err := q.channel.Consume(ScrapeResultQueue, "", false, false, false, false, nil)
	if err != nil {
		return nil, fmt.Errorf("consume %s: %w", ScrapeResultQueue, err)
	}

	results := make(chan models.ScrapeResult, 10)

	go func() {
		defer close(results)
		for {
			select {
			case <-ctx.Done():
				return
			case msg, ok := <-msgs:
				if !ok {
					return
				}
				var result models.ScrapeResult
				if err := json.Unmarshal(msg.Body, &result); err != nil {
					log.Printf("[queue] failed to unmarshal scrape result: %v", err)
					msg.Nack(false, false)
					continue
				}
				msg.Ack(false)
				results <- result
			}
		}
	}()

	return results, nil
}

// Ping checks if RabbitMQ is reachable.
func (q *QueueService) Ping() error {
	if q.conn.IsClosed() {
		return fmt.Errorf("rabbitmq connection closed")
	}
	return nil
}

// Close tears down the connection.
func (q *QueueService) Close() {
	if q.channel != nil {
		q.channel.Close()
	}
	if q.conn != nil {
		q.conn.Close()
	}
}
