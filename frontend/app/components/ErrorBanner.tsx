"use client";

interface ErrorBannerProps {
  message: string;
  onDismiss: () => void;
}

export default function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div className="error-banner" role="alert">
      <span className="error-banner__icon" aria-hidden="true">&#9888;</span>
      <span className="error-banner__message">{message}</span>
      <button
        className="error-banner__dismiss"
        onClick={onDismiss}
        aria-label="Dismiss error"
      >
        &#x2715;
      </button>
    </div>
  );
}
