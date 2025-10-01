import React, { useState, useEffect, useRef } from 'react';
import { Plus, Play, Square, Trash2, FolderGit2, GitBranch, Clock, Activity, AlertCircle, CheckCircle, WifiOff, Wifi, RefreshCw } from 'lucide-react';

class ApiService {
  constructor() {
    this.baseURL = 'http://localhost:8001';
  }
  
  async getRepositories() {
    const response = await fetch(`${this.baseURL}/repos`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
  
  async addRepository(repoData) {
    const response = await fetch(`${this.baseURL}/repos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(repoData)
    });
    if (!response.ok) {
      const error = await response.text();
      throw new Error(error);
    }
    return response.json();
  }
  
  async removeRepository(repoId) {
    const response = await fetch(`${this.baseURL}/repos/${repoId}`, {
      method: 'DELETE'
    });
    return response.ok;
  }
  
  async startWatching(repoId) {
    const response = await fetch(`${this.baseURL}/repos/${repoId}/start`, {
      method: 'POST'
    });
    return response.ok;
  }
  
  async stopWatching(repoId) {
    const response = await fetch(`${this.baseURL}/repos/${repoId}/stop`, {
      method: 'POST'
    });
    return response.ok;
  }
  
  async getRecentChanges(limit = 50) {
    const response = await fetch(`${this.baseURL}/changes?limit=${limit}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
  
  async getHealth() {
    const response = await fetch(`${this.baseURL}/health`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
}

const apiService = new ApiService();

const useWebSocket = (url) => {
  const [liveChanges, setLiveChanges] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const ws = useRef(null);
  const reconnectTimeout = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  
  const connectWebSocket = () => {
    if (reconnectAttempts.current >= maxReconnectAttempts) {
      setConnectionStatus('failed');
      return;
    }
    
    try {
      setConnectionStatus('connecting');
      ws.current = new WebSocket(url);
      
      ws.current.onopen = () => {
        setConnectionStatus('connected');
        reconnectAttempts.current = 0;
        console.log('WebSocket connected');
      };
      
      ws.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('WebSocket message:', message);
          
          if (message.type === 'file_change' && message.data) {
            setLiveChanges(prev => [message.data, ...prev.slice(0, 49)]);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
      
      ws.current.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setConnectionStatus('disconnected');
        
        // Only reconnect if it wasn't a manual close
        if (event.code !== 1000) {
          reconnectAttempts.current++;
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 10000);
          reconnectTimeout.current = setTimeout(connectWebSocket, delay);
        }
      };
      
      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionStatus('error');
      };
    } catch (error) {
      console.error('WebSocket connection error:', error);
      setConnectionStatus('error');
    }
  };
  
  useEffect(() => {
    connectWebSocket();
    
    return () => {
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
      if (ws.current) {
        ws.current.close(1000, 'Component unmounting');
      }
    };
  }, [url]);
  
  const reconnect = () => {
    reconnectAttempts.current = 0;
    connectWebSocket();
  };
  
  return { liveChanges, connectionStatus, reconnect };
};

const useChanges = () => {
  const [existingChanges, setExistingChanges] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastFetch, setLastFetch] = useState(null);
  
  const fetchChanges = async () => {
    setLoading(true);
    setError(null);
    try {
      const changes = await apiService.getRecentChanges(50);
      setExistingChanges(changes);
      setLastFetch(new Date());
    } catch (error) {
      console.error('Failed to fetch changes:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };
  
  useEffect(() => {
    fetchChanges();
    // Refresh every 30 seconds
    const interval = setInterval(fetchChanges, 30000);
    return () => clearInterval(interval);
  }, []);
  
  return {
    existingChanges,
    loading,
    error,
    lastFetch,
    refetch: fetchChanges
  };
};

const useRepoManager = () => {
  const [repositories, setRepositories] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const fetchRepositories = async () => {
    setLoading(true);
    setError(null);
    try {
      const repos = await apiService.getRepositories();
      setRepositories(repos);
    } catch (error) {
      console.error('Failed to fetch repositories:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };
  
  const addRepo = async (repoData) => {
    try {
      const newRepo = await apiService.addRepository(repoData);
      setRepositories(prev => [...prev, newRepo]);
      return { success: true };
    } catch (error) {
      console.error('Failed to add repository:', error);
      return { success: false, error: error.message };
    }
  };
  
  const removeRepo = async (repoId) => {
    try {
      await apiService.removeRepository(repoId);
      setRepositories(prev => prev.filter(repo => repo.id !== repoId));
      return true;
    } catch (error) {
      console.error('Failed to remove repository:', error);
      return false;
    }
  };
  
  const toggleWatching = async (repoId) => {
    const repo = repositories.find(r => r.id === repoId);
    try {
      if (repo.is_watching) {
        await apiService.stopWatching(repoId);
      } else {
        await apiService.startWatching(repoId);
      }
      
      setRepositories(prev => 
        prev.map(r => 
          r.id === repoId 
            ? { ...r, is_watching: !r.is_watching }
            : r
        )
      );
      return true;
    } catch (error) {
      console.error('Failed to toggle watching:', error);
      return false;
    }
  };
  
  useEffect(() => {
    fetchRepositories();
  }, []);
  
  return {
    repositories,
    loading,
    error,
    addRepo,
    removeRepo,
    toggleWatching,
    refreshRepos: fetchRepositories
  };
};

const ConnectionStatus = ({ status, onReconnect }) => {
  const getStatusConfig = () => {
    switch (status) {
      case 'connected':
        return { icon: Wifi, color: 'text-success', text: 'Live Feed Connected' };
      case 'connecting':
        return { icon: RefreshCw, color: 'text-warning', text: 'Connecting...', spin: true };
      case 'disconnected':
        return { icon: WifiOff, color: 'text-warning', text: 'Reconnecting...' };
      case 'error':
        return { icon: AlertCircle, color: 'text-danger', text: 'Connection Error' };
      case 'failed':
        return { icon: AlertCircle, color: 'text-danger', text: 'Connection Failed', showReconnect: true };
      default:
        return { icon: WifiOff, color: 'text-muted', text: 'Unknown' };
    }
  };
  
  const { icon: Icon, color, text, spin, showReconnect } = getStatusConfig();
  
  return (
    <div className={`d-flex align-items-center gap-2 ${color}`}>
      <Icon size={14} className={spin ? 'spin' : ''} />
      <span className="small fw-medium d-none d-sm-inline">{text}</span>
      {showReconnect && (
        <button 
          className="btn btn-sm btn-outline-primary" 
          onClick={onReconnect}
          title="Retry connection"
        >
          <RefreshCw size={12} />
        </button>
      )}
    </div>
  );
};

const AddRepoForm = ({ onAdd, onCancel }) => {
  const [formData, setFormData] = useState({ name: '', path: '' });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.path.trim()) {
      setError('Please fill in all fields');
      return;
    }

    setSubmitting(true);
    setError('');

    const result = await onAdd(formData);
    if (result.success) {
      setFormData({ name: '', path: '' });
      onCancel();
    } else {
      setError(result.error || 'Failed to add repository');
    }

    setSubmitting(false);
  };

  return (
    <div
      className="modal show d-block"
      style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
    >
      <div className="modal-dialog modal-dialog-centered">
        <div className="modal-content">
          <form onSubmit={handleSubmit}>
            <div className="modal-header">
              <h5 className="modal-title">Add Repository</h5>
              <button
                type="button"
                className="btn-close"
                onClick={onCancel}
                disabled={submitting}
              ></button>
            </div>
            <div className="modal-body">
              {error && (
                <div className="alert alert-danger" role="alert">
                  {error}
                </div>
              )}

              <div className="mb-3">
                <label className="form-label">Repository Name</label>
                <input
                  type="text"
                  className="form-control"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  disabled={submitting}
                />
              </div>

              <div className="mb-3">
                <label className="form-label">Repository Path</label>
                <input
                  type="text"
                  className="form-control"
                  value={formData.path}
                  onChange={(e) =>
                    setFormData({ ...formData, path: e.target.value })
                  }
                  disabled={submitting}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onCancel}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={submitting}
              >
                {submitting ? 'Adding...' : 'Add Repository'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

const RepoCard = ({ repo, onRemove, onToggleWatching }) => {
  const [actionLoading, setActionLoading] = useState(false);
  
  const handleToggleWatching = async () => {
    setActionLoading(true);
    await onToggleWatching(repo.id);
    setActionLoading(false);
  };
  
  const handleRemove = async () => {
    if (confirm(`Are you sure you want to remove "${repo.name}"?`)) {
      setActionLoading(true);
      await onRemove(repo.id);
      setActionLoading(false);
    }
  };
  
  return (
    <div className="card mb-3">
      <div className="card-body">
        <div className="d-flex flex-column flex-sm-row justify-content-between align-items-start">
          <div className="flex-grow-1 w-100">
            <div className="d-flex align-items-center mb-2">
              <FolderGit2 size={20} className="text-primary me-2 flex-shrink-0" />
              <h6 className="card-title mb-0 me-2 text-truncate">{repo.name}</h6>
              {repo.is_watching ? (
                <CheckCircle size={16} className="text-success flex-shrink-0" />
              ) : (
                <div className="border border-secondary rounded-circle flex-shrink-0" style={{ width: '16px', height: '16px' }}></div>
              )}
            </div>
            
            <p className="card-text text-muted small font-monospace mb-2 text-break">
              {repo.path}
            </p>
            
            <div className="d-flex flex-wrap gap-2 gap-sm-3 text-muted small mb-3 mb-sm-0">
              <span className="d-flex align-items-center gap-1">
                <Activity size={12} />
                {repo.total_changes} changes
              </span>
              {repo.last_change && (
                <span className="d-flex align-items-center gap-1">
                  <Clock size={12} />
                  {new Date(repo.last_change).toLocaleDateString()}
                </span>
              )}
            </div>
          </div>
          
          <div className="d-flex gap-2 align-self-end align-self-sm-start mt-2 mt-sm-0">
            <button
              className={`btn btn-sm ${repo.is_watching ? 'btn-outline-danger' : 'btn-outline-success'}`}
              onClick={handleToggleWatching}
              disabled={actionLoading}
              title={repo.is_watching ? 'Stop watching' : 'Start watching'}
            >
              {repo.is_watching ? <Square size={16} /> : <Play size={16} />}
            </button>
            
            <button
              className="btn btn-sm btn-outline-secondary"
              onClick={handleRemove}
              disabled={actionLoading}
              title="Remove repository"
            >
              <Trash2 size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const ChangeItem = ({ change, isLive = false }) => {
  const [showDiff, setShowDiff] = useState(false);
  
  const getChangeTypeBadge = (type) => {
    switch (type) {
      case 'created': return 'bg-success';
      case 'modified': return 'bg-primary';
      case 'deleted': return 'bg-danger';
      default: return 'bg-secondary';
    }
  };
  
  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
  };

  // Check if we have diff content to show
  const hasDiffContent = () => {
    if (!change.git_diff) return false;
    
    const excludedMessages = [
      'No changes detected',
      'No actual changes detected', 
      'No changes to display',
      'File deleted (no previous snapshot available)',
      ''
    ];
    
    return !excludedMessages.includes(change.git_diff.trim());
  };

  // Format git diff for better display
  const formatGitDiff = (diff) => {
    if (!diff) return '';
    
    // Split into lines and process each line
    const lines = diff.split('\n');
    let formattedLines = [];
    
    for (const line of lines) {
      if (line.startsWith('+++') || line.startsWith('---')) {
        // File headers
        formattedLines.push(`<span class="text-info">${line}</span>`);
      } else if (line.startsWith('@@')) {
        // Hunk headers
        formattedLines.push(`<span class="text-warning fw-bold">${line}</span>`);
      } else if (line.startsWith('+')) {
        // Added lines
        formattedLines.push(`<span class="text-success">${line}</span>`);
      } else if (line.startsWith('-')) {
        // Removed lines
        formattedLines.push(`<span class="text-danger">${line}</span>`);
      } else if (line.startsWith('diff --git')) {
        // Git diff header
        formattedLines.push(`<span class="text-muted fw-bold">${line}</span>`);
      } else {
        // Context lines
        formattedLines.push(`<span class="text-dark">${line}</span>`);
      }
    }
    
    return formattedLines.join('\n');
  };
  
  return (
    <div className={`card mb-3 ${isLive ? 'border-success border-2' : 'border-start border-primary border-4'}`}>
      <div className="card-body">
        <div className="d-flex flex-column flex-sm-row justify-content-between align-items-start">
          <div className="flex-grow-1 w-100">
            <div className="d-flex flex-wrap align-items-center mb-2 gap-2">
              <span className={`badge ${getChangeTypeBadge(change.change_type)} flex-shrink-0`}>
                {change.change_type.toUpperCase()}
              </span>
              <small className="text-muted text-truncate">
                {change.repository_name}
              </small>
              {isLive && (
                <span className="badge bg-success">LIVE</span>
              )}
            </div>
            
            <h6 className="font-monospace mb-2 text-break">
              {change.relative_path}
            </h6>
            
            <div className="d-flex flex-wrap gap-2 gap-sm-3 text-muted small mb-2">
              <span className="text-truncate">{change.author}</span>
              <span className="flex-shrink-0">{formatTime(change.timestamp)}</span>
              {(change.lines_added > 0 || change.lines_removed > 0) && (
                <span className="flex-shrink-0">
                  <span className="text-success">+{change.lines_added}</span>
                  {' '}
                  <span className="text-danger">-{change.lines_removed}</span>
                </span>
              )}
            </div>

            {/* Toggle button for diff */}
            {hasDiffContent() && (
              <button 
                className="btn btn-sm btn-outline-secondary mb-2"
                onClick={() => setShowDiff(!showDiff)}
              >
                {showDiff ? '🔽 Hide Diff' : '🔽 Show Diff'}
              </button>
            )}
          </div>
        </div>
        
        {/* Show formatted_changes if available (fallback) */}
        {!hasDiffContent() && change.formatted_changes && 
         change.formatted_changes !== 'No changes to display' && 
         change.formatted_changes !== 'No changes detected' && (
          <div className="mt-3">
            <div className="bg-light p-3 rounded overflow-auto" style={{ maxHeight: '12rem' }}>
              <pre className="mb-0 small font-monospace text-wrap">{change.formatted_changes}</pre>
            </div>
          </div>
        )}

        {/* Show git diff when toggled */}
        {showDiff && hasDiffContent() && (
          <div className="mt-3">
            <div className="card">
              <div className="card-header py-2">
                <small className="text-muted fw-bold">Git Diff</small>
              </div>
              <div className="card-body p-0">
                <div 
                  className="bg-dark text-light p-3 overflow-auto font-monospace small" 
                  style={{ maxHeight: '20rem' }}
                  dangerouslySetInnerHTML={{ 
                    __html: formatGitDiff(change.git_diff) 
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Debug info for development */}
        {process.env.NODE_ENV === 'development' && (
          <div className="mt-2">
            <details className="small text-muted">
              <summary>Debug Info</summary>
              <pre className="small">
                {JSON.stringify({
                  has_git_diff: !!change.git_diff,
                  git_diff_length: change.git_diff?.length || 0,
                  has_formatted_changes: !!change.formatted_changes,
                  formatted_changes_length: change.formatted_changes?.length || 0,
                  sent_to_ai: change.sent_to_ai
                }, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </div>
    </div>
  );
};

const ChangesFeed = ({ existingChanges, liveChanges, loading, error, lastFetch, onRefresh }) => {
  // Merge and deduplicate changes (live changes first, then existing)
  const allChanges = React.useMemo(() => {
    const changeMap = new Map();

    // Add live changes first (they take precedence)
    liveChanges.forEach(change => {
      const key = `${change.relative_path}-${change.timestamp}`;
      changeMap.set(key, { ...change, isLive: true });
    });

    // Add existing changes if not already present
    existingChanges.forEach(change => {
      const key = `${change.relative_path}-${change.timestamp}`;
      if (!changeMap.has(key)) {
        changeMap.set(key, { ...change, isLive: false });
      }
    });

    // Sort by timestamp (newest first)
    return Array.from(changeMap.values())
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }, [existingChanges, liveChanges]);

  return (
    <div className="card h-100 d-flex flex-column">
      {/* Card header */}
      <div className="card-header d-flex flex-column flex-sm-row justify-content-between align-items-start align-items-sm-center gap-2">
        <div>
          <h5 className="card-title mb-0">File Changes</h5>
          {lastFetch && (
            <small className="text-muted">
              Last updated: {lastFetch.toLocaleTimeString()}
            </small>
          )}
        </div>

        <div className="d-flex align-items-center gap-2">
          <small className="text-muted">
            {allChanges.length} changes
            {liveChanges.length > 0 && (
              <span className="text-success ms-1">({liveChanges.length} live)</span>
            )}
          </small>
          <button 
            className="btn btn-sm btn-outline-primary"
            onClick={onRefresh}
            disabled={loading}
            title="Refresh changes"
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {/* Card body - scrollable */}
      <div className="card-body p-0 flex-grow-1 d-flex flex-column">
        <div className="p-3 overflow-auto flex-grow-1">
          {error && (
            <div className="alert alert-warning mb-3 d-flex align-items-center" role="alert">
              <AlertCircle size={16} className="me-2" />
              Failed to load changes: {error}
            </div>
          )}

          {loading && allChanges.length === 0 ? (
            <div className="text-center py-4">
              <div className="spinner-border text-primary mb-3" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
              <p className="text-muted mb-0">Loading changes...</p>
            </div>
          ) : allChanges.length > 0 ? (
            allChanges.map((change, index) => (
              <ChangeItem 
                key={`${change.relative_path}-${change.timestamp}-${index}`} 
                change={change} 
                isLive={change.isLive}
              />
            ))
          ) : (
            <div className="text-center py-5 text-muted">
              <Activity size={48} className="mb-3 opacity-50" />
              <p className="mb-1">No changes detected yet</p>
              <small>Start watching repositories to see file changes</small>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const RepoManager = ({ repositories, onAddRepo, onRemoveRepo, onToggleWatching, loading, error }) => {
  const [showAddForm, setShowAddForm] = useState(false);
  
  return (
    <div className="card h-100">
      <div className="card-header">
        <div className="d-flex justify-content-between align-items-center">
          <h5 className="card-title mb-0">Repositories</h5>
          <button 
            className="btn btn-primary btn-sm d-flex align-items-center gap-1"
            onClick={() => setShowAddForm(true)}
          >
            <Plus size={14} />
            <span className="d-none d-sm-inline">Add Repo</span>
            <span className="d-sm-none">Add</span>
          </button>
        </div>
      </div>
      <div className="card-body">
        {error && (
          <div className="alert alert-warning mb-3" role="alert">
            <AlertCircle size={16} className="me-2" />
            Failed to load repositories: {error}
          </div>
        )}
        
        {loading ? (
          <div className="text-center py-4">
            <div className="spinner-border text-primary mb-3" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
            <p className="text-muted mb-0">Loading repositories...</p>
          </div>
        ) : repositories.length > 0 ? (
          <div>
            {repositories.map(repo => (
              <RepoCard 
                key={repo.id}
                repo={repo}
                onRemove={onRemoveRepo}
                onToggleWatching={onToggleWatching}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-4 text-muted">
            <FolderGit2 size={40} className="mb-3 opacity-50" />
            <p className="mb-1">No repositories added yet</p>
            <small>Add a git repository to start monitoring</small>
          </div>
        )}
      </div>
      
      {showAddForm && (
        <AddRepoForm 
          onAdd={onAddRepo}
          onCancel={() => setShowAddForm(false)}
        />
      )}
    </div>
  );
};

const Header = ({ connectionStatus, onReconnect }) => {
  return (
    <header className="w-100 bg-white border-bottom position-sticky top-0" style={{ zIndex: 1000 }}>
      <div className="w-100 px-3 py-3">
        <div className="d-flex align-items-center justify-content-between w-100">
          <div className="d-flex align-items-center flex-grow-1">
            <GitBranch className="text-primary me-2 me-sm-3" size={24} />
            <div className="d-none d-sm-block">
              <h1 className="mb-0 h4">Watcher Service</h1>
              <small className="text-muted">AI-Powered Testing Companion</small>
            </div>
            <div className="d-sm-none">
              <h1 className="mb-0 h5">Watcher</h1>
            </div>
          </div>
          
          <div className="d-flex align-items-center">
            <ConnectionStatus status={connectionStatus} onReconnect={onReconnect} />
          </div>
        </div>
      </div>
    </header>
  );
};

const Dashboard = () => {
  const { repositories, loading: reposLoading, error: reposError, addRepo, removeRepo, toggleWatching } = useRepoManager();
  const { liveChanges, connectionStatus, reconnect } = useWebSocket('ws://localhost:8001/ws/live-feed');
  const { existingChanges, loading: changesLoading, error: changesError, lastFetch, refetch } = useChanges();
  
  // Inject Bootstrap CSS and custom styles
  useEffect(() => {
    const existingLink = document.querySelector('link[href*="bootstrap"]');
    if (!existingLink) {
      const link = document.createElement('link');
      link.href = 'https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.2/css/bootstrap.min.css';
      link.rel = 'stylesheet';
      document.head.appendChild(link);
    }
    
    const style = document.createElement('style');
    style.textContent = `
      .spin { animation: spin 1s linear infinite; }
      @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      body { 
        margin: 0; 
        padding: 0; 
        background-color: #f8f9fa !important; 
      }
      html {
        background-color: #f8f9fa !important;
      }
      .main-container {
        background-color: #f8f9fa;
        min-height: 100vh;
      }
      /* Ensure header is truly 100% width */
      .full-width-header {
        width: 100vw !important;
        margin-left: calc(-50vw + 50%) !important;
        position: relative;
        left: 50%;
        right: 50%;
      }
      /* GitHub-style diff styling */
      .diff-view {
        background-color: #1e293b; /* Dark slate */
        color: #e2e8f0;
        font-family: monospace;
        font-size: 0.85rem;
        line-height: 1.4;
        border-radius: 0.5rem;
      }
      .diff-view .text-success { color: #22c55e; }
      .diff-view .text-danger { color: #ef4444; }
      .diff-view .text-warning { color: #facc15; }
      .diff-view .text-info { color: #38bdf8; }
    `;
    document.head.appendChild(style);
  }, []);
  
  return (
    <div className="main-container vh-100 d-flex flex-column">
      {/* Fixed Header - Now 100% width */}
      <Header connectionStatus={connectionStatus} onReconnect={reconnect} />
      
      {/* Main Content Area */}
      <div className="container-fluid py-4 bg-light">
        <div className="row g-4">
          {/* Repository Management - Fixed */}
          <div className="col-12 col-md-4 col-lg-4">
            <RepoManager 
              repositories={repositories}
              onAddRepo={addRepo}
              onRemoveRepo={removeRepo}
              onToggleWatching={toggleWatching}
              loading={reposLoading}
              error={reposError}
            />
          </div>

          <div className="col-12 col-md-8 col-lg-8">
            <ChangesFeed 
              existingChanges={existingChanges}
              liveChanges={liveChanges}
              loading={changesLoading}
              error={changesError}
              lastFetch={lastFetch}
              onRefresh={refetch}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;