"use client";

/**
 * ErrorBoundary — React class-based Error Boundary for Certinator AI.
 *
 * Catches render-time errors thrown by any child component tree (including
 * CopilotKit's internal rendering) and surfaces a recovery UI so the page
 * never shows a blank white screen.
 *
 * Usage:
 *   <ErrorBoundary resetOnChange={messages.length}>
 *     <CertinatorHooks ... />
 *     <CopilotChat ... />
 *   </ErrorBoundary>
 *
 * `resetOnChange` — when this value changes the boundary resets automatically,
 * allowing recovery after a new message arrives even without a user click.
 */

import React, { type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  /** Custom fallback renderer. Receives the caught error and a reset callback. */
  fallback?: (error: Error, reset: () => void) => React.ReactNode;
  /**
   * When this value changes (e.g. message count increments) the boundary
   * resets itself, clearing the error state automatically.
   */
  resetOnChange?: unknown;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export default class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[CertinatorAI] Uncaught render error:", error, info);
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (
      prevProps.resetOnChange !== this.props.resetOnChange &&
      this.state.error !== null
    ) {
      this.setState({ error: null });
    }
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    const { children, fallback } = this.props;

    if (error) {
      if (fallback) return fallback(error, this.reset);

      return (
        <div className="error-boundary-fallback">
          <p className="error-boundary-fallback__title">Something went wrong</p>
          <p className="error-boundary-fallback__message">{error.message}</p>
          <button
            className="error-boundary-fallback__reset"
            onClick={this.reset}
          >
            Try again
          </button>
        </div>
      );
    }

    return children;
  }
}
