import React, { useState } from 'react';
import { submitGeneralFeedback } from '../services/monitoringApi';
import { UserFeedbackPayload } from '../types/monitoring';

interface UserFeedbackModalProps {
  isOpen: boolean;
  token: string | null;
  onClose: () => void;
}

export const UserFeedbackModal: React.FC<UserFeedbackModalProps> = ({ isOpen, token, onClose }) => {
  const [rating, setRating] = useState<number>(5);
  const [feedbackType, setFeedbackType] = useState<UserFeedbackPayload['feedback_type']>('general');
  const [comment, setComment] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [submitted, setSubmitted] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setError('Please log in to submit feedback.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await submitGeneralFeedback(token, {
        rating,
        feedback_type: feedbackType,
        comment: comment.trim() || undefined,
      });
      setSubmitted(true);
      setTimeout(() => {
        setSubmitted(false);
        setComment('');
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err?.message || 'Failed to submit feedback.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="feedback-modal-overlay">
      <div className="feedback-modal-content">
        <div className="feedback-modal-header">
          <h3>Send Product Feedback</h3>
          <button className="close-btn" onClick={onClose} aria-label="Close">×</button>
        </div>

        {submitted ? (
          <div className="feedback-success-message">
            <span className="success-icon">✓</span>
            <p>Thank you for your feedback! We appreciate your input.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="feedback-form">
            {error && <div className="feedback-error">{error}</div>}

            <div className="form-group">
              <label>How satisfied are you with AskMyData?</label>
              <div className="rating-stars">
                {[1, 2, 3, 4, 5].map((star) => (
                  <button
                    key={star}
                    type="button"
                    className={`star-btn ${star <= rating ? 'active' : ''}`}
                    onClick={() => setRating(star)}
                  >
                    ★
                  </button>
                ))}
              </div>
            </div>

            <div className="form-group">
              <label>Category</label>
              <select
                value={feedbackType}
                onChange={(e) => setFeedbackType(e.target.value as any)}
                className="feedback-select"
              >
                <option value="general">General Feedback</option>
                <option value="usability">Usability / Design</option>
                <option value="feature_request">Feature Request</option>
                <option value="incorrect_answer">Incorrect AI Answer</option>
                <option value="bug">Report a Bug</option>
              </select>
            </div>

            <div className="form-group">
              <label>Comments (optional)</label>
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="Tell us what you liked or how we can improve..."
                rows={4}
                className="feedback-textarea"
                maxLength={2000}
              />
            </div>

            <div className="feedback-modal-actions">
              <button type="button" className="btn-secondary" onClick={onClose} disabled={submitting}>
                Cancel
              </button>
              <button type="submit" className="btn-primary" disabled={submitting}>
                {submitting ? 'Submitting...' : 'Submit Feedback'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
