import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  /**
   * silent=true 用于**装饰性**子树（樱花、鼠标拖尾、看板娘…）。
   * 这类组件出错不该把整页换成崩溃界面，静默降级成「什么都不渲染」即可，
   * 正文内容仍然可用。
   */
  silent?: boolean;
  /** 自定义兜底 UI；给了它就完全接管渲染 */
  fallback?: ReactNode;
}
interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('fufu crashed:', error, info);
  }

  private reset = () => {
    this.setState({ error: null });
    window.location.reload();
  };

  render() {
    const { error } = this.state;

    if (error) {
      if (this.props.silent) return null;
      if (this.props.fallback !== undefined) return this.props.fallback;

      return (
        <div className="min-h-screen flex items-center justify-center bg-fufu-cream p-8">
          <div className="max-w-lg text-center">
            <p className="text-6xl mb-4 animate-float">😿</p>
            <h1 className="font-cute text-2xl mb-4 text-fufu-text">哎呀，fufu 摔了一跤...</h1>
            <div className="bg-fufu-error-light/30 border border-fufu-error/20 rounded-fufu-card p-4 mb-4 text-left">
              <p className="font-body text-sm text-fufu-text break-all">{error.message}</p>
            </div>
            <button onClick={this.reset} className="fufu-btn-primary">
              重新加载 💕
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
