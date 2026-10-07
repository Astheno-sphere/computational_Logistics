import { Component, type ErrorInfo, type ReactNode } from "react";
import { logFrontendEvent } from "@unfour/command-client";
import { ErrorState, useI18n } from "@unfour/ui";

type BoundaryProps = {
  children: ReactNode;
  description: string;
  title: string;
};

type BoundaryState = {
  error: Error | null;
};

class DesktopErrorBoundaryInner extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    void logFrontendEvent({
      level: "error",
      event: "react_error_boundary",
      module: "frontend",
      operation: "render",
      fields: {
        message: error.message,
        componentStack: info.componentStack,
      },
    });
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-screen items-center justify-center bg-[var(--u-color-bg)] p-6">
          <ErrorState className="max-w-md flex-col gap-1">
            <strong className="font-semibold">{this.props.title}</strong>
            <span>{this.props.description}</span>
          </ErrorState>
        </div>
      );
    }

    return this.props.children;
  }
}

export function DesktopErrorBoundary({ children }: { children: ReactNode }) {
  const { t } = useI18n();

  return (
    <DesktopErrorBoundaryInner
      description={t("app.errorBoundary.description")}
      title={t("app.errorBoundary.title")}
    >
      {children}
    </DesktopErrorBoundaryInner>
  );
}
