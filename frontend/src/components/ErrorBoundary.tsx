/**
 * Render-error boundaries (audit F-15). Without one, a throw anywhere in the tree unmounts the whole app and leaves
 * a blank page. The app-level boundary offers a reload; the card-level one keeps the viewer running when a single
 * side-panel card fails.
 */
import { Component, type ErrorInfo, type ReactNode } from "react";
import { href } from "../lib/base";

interface Props { children: ReactNode; fallback?: (error: Error, reset: () => void) => ReactNode; label?: string }
interface State { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[ParallaX] ${this.props.label ?? "render"} failed`, error, info.componentStack);
  }

  reset = (): void => this.setState({ error: null });

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;
    if (this.props.fallback) return this.props.fallback(error, this.reset);
    return (
      <div className="notice error-card" role="alert">
        <p>{this.props.label ? `${this.props.label}: ` : ""}this part of the page could not be shown ({error.message}).</p>
        <button onClick={this.reset}>Try again</button>
      </div>
    );
  }
}

/** Whole-app fallback: the page cannot continue, so say so and offer a reload. */
export function AppCrash({ error }: { error: Error }) {
  return (
    <main className="app-crash" role="alert">
      <h1>Something went wrong</h1>
      <p>ParallaX hit an error it could not recover from: <code>{error.message}</code></p>
      <p><button className="primary" onClick={() => location.reload()}>Reload the page</button>{" "}
        <a className="button" href={href()}>Back to the start</a></p>
    </main>
  );
}
