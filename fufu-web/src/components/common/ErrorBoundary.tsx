import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props { children: ReactNode; }
interface State { error: Error | null; }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('fufu crashed:', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-fufu-cream p-8">
          <div className="max-w-lg text-center">
            <p className="text-6xl mb-4 animate-float">😿</p>
            <h1 className="font-cute text-2xl mb-4 text-fufu-text">
              哎呀，fufu 摔了一跤...
            </h1>
            <div className="bg-fufu-error-light/30 border border-fufu-error/20 rounded-fufu-card p-4 mb-4 text-left">
              <p className="font-body text-sm text-fufu-text break-all">
                {this.state.error.message}
              </p>
            </div>
            <button
              onClick={() => {
                this.setState({ error: null });
                window.location.reload();
              }}
              className="fufu-btn-primary"
            >
              重新加载 💕
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
