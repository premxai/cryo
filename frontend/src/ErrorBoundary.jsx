import { Component } from 'react'

/**
 * ErrorBoundary — catches rendering errors in the results list.
 * Prevents a single bad result from crashing the whole search UI.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, message: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, message: error?.message || 'Unknown error' }
  }

  componentDidCatch(error, info) {
    console.error('[Cryo] ResultCard render error:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="border border-red-500/20 bg-red-900/10 p-4 font-mono text-sm text-red-400/70">
          <span className="text-red-500/50">render error: </span>
          {this.state.message}
        </div>
      )
    }
    return this.props.children
  }
}
