import React, { useState, useEffect, useRef } from 'react';
import { Activity, Folder, Play, Square, Trash2, Plus, RefreshCw, Database, Wifi, WifiOff, Code, FileText, AlertCircle, CheckCircle, Clock, User } from 'lucide-react';

const API_URL = 'http://localhost:8001';
const WS_URL = 'ws://localhost:8001/ws/live-feed';

export default function WatcherDashboard() {
  const [repos, setRepos] = useState([]);
  const [changes, setChanges] = useState([]);
  const [stats, setStats] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('repositories');
  const [showAddRepo, setShowAddRepo] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState(null);
  
  const wsRef = useRef(null);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    loadRepositories();
    loadChanges();
    loadStats();
    
    const interval = setInterval(() => {
      loadStats();
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);

  const connectWebSocket = () => {
    try {
      const ws = new WebSocket(WS_URL);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setWsConnected(true);
      };
      
      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        
        if (message.type === 'file_change') {
          setChanges(prev => [message.data, ...prev].slice(0, 100));
          loadRepositories();
        }
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setWsConnected(false);
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setWsConnected(false);
        setTimeout(connectWebSocket, 5000);
      };
      
      wsRef.current = ws;
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      setWsConnected(false);
    }
  };

  const loadRepositories = async () => {
    try {
      const response = await fetch(`${API_URL}/repos`);
      const data = await response.json();
      setRepos(data);
      setLoading(false);
    } catch (error) {
      console.error('Error loading repositories:', error);
      setLoading(false);
    }
  };

  const loadChanges = async (repoId = null) => {
    try {
      const url = repoId 
        ? `${API_URL}/changes?repository_id=${repoId}&limit=50`
        : `${API_URL}/changes?limit=50`;
      const response = await fetch(url);
      const data = await response.json();
      setChanges(data);
    } catch (error) {
      console.error('Error loading changes:', error);
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch(`${API_URL}/stats`);
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  };

  const startWatching = async (repoId) => {
    try {
      await fetch(`${API_URL}/repos/${repoId}/start`, { method: 'POST' });
      loadRepositories();
    } catch (error) {
      console.error('Error starting watcher:', error);
    }
  };

  const stopWatching = async (repoId) => {
    try {
      await fetch(`${API_URL}/repos/${repoId}/stop`, { method: 'POST' });
      loadRepositories();
    } catch (error) {
      console.error('Error stopping watcher:', error);
    }
  };

  const deleteRepo = async (repoId) => {
    if (!confirm('Are you sure you want to remove this repository?')) return;
    
    try {
      await fetch(`${API_URL}/repos/${repoId}`, { method: 'DELETE' });
      loadRepositories();
      setSelectedRepo(null);
    } catch (error) {
      console.error('Error deleting repository:', error);
    }
  };

  const getChangeTypeColor = (type) => {
    switch (type) {
      case 'created': return 'text-green-600 bg-green-50';
      case 'modified': return 'text-blue-600 bg-blue-50';
      case 'deleted': return 'text-red-600 bg-red-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now - date;
    
    if (diff < 60000) return 'just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <header className="bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                <Activity className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900">Watcher Service</h1>
                <p className="text-sm text-slate-500">AI-Powered Testing Companion</p>
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${wsConnected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                {wsConnected ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
                {wsConnected ? 'Live' : 'Disconnected'}
              </div>
              
              {stats && (
                <div className="flex items-center gap-4 text-sm">
                  <div className="flex items-center gap-2">
                    <Folder className="w-4 h-4 text-slate-400" />
                    <span className="font-medium text-slate-700">{stats.watcher_statistics.total_repositories}</span>
                    <span className="text-slate-500">repos</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-slate-400" />
                    <span className="font-medium text-slate-700">{stats.change_statistics.total_changes}</span>
                    <span className="text-slate-500">changes</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 mt-6">
        <div className="flex gap-2 border-b border-slate-200">
          <button
            onClick={() => setActiveTab('repositories')}
            className={`px-4 py-2 font-medium transition-colors ${
              activeTab === 'repositories'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Repositories
          </button>
          <button
            onClick={() => setActiveTab('changes')}
            className={`px-4 py-2 font-medium transition-colors ${
              activeTab === 'changes'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Live Changes
          </button>
          <button
            onClick={() => setActiveTab('statistics')}
            className={`px-4 py-2 font-medium transition-colors ${
              activeTab === 'statistics'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Statistics
          </button>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {activeTab === 'repositories' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold text-slate-900">Repositories</h2>
              <button
                onClick={() => setShowAddRepo(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Repository
              </button>
            </div>

            {loading ? (
              <div className="text-center py-12">
                <RefreshCw className="w-8 h-8 text-slate-400 animate-spin mx-auto" />
                <p className="text-slate-500 mt-2">Loading repositories...</p>
              </div>
            ) : repos.length === 0 ? (
              <div className="bg-white rounded-xl p-12 text-center border border-slate-200">
                <Folder className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-slate-900 mb-2">No repositories yet</h3>
                <p className="text-slate-500 mb-6">Add a repository to start watching for changes</p>
                <button
                  onClick={() => setShowAddRepo(true)}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Add Your First Repository
                </button>
              </div>
            ) : (
              <div className="grid gap-4">
                {repos.map(repo => (
                  <div
                    key={repo.id}
                    className="bg-white rounded-xl p-6 border border-slate-200 hover:border-blue-300 transition-all hover:shadow-md"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <Folder className="w-5 h-5 text-blue-600" />
                          <h3 className="text-lg font-semibold text-slate-900">{repo.name}</h3>
                          {repo.is_watching && (
                            <span className="px-2 py-1 bg-green-100 text-green-700 text-xs font-medium rounded-full flex items-center gap-1">
                              <Activity className="w-3 h-3" />
                              Watching
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-slate-500 font-mono mb-3">{repo.path}</p>
                        
                        <div className="flex items-center gap-6 text-sm text-slate-600">
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4" />
                            <span>{repo.total_changes} changes</span>
                          </div>
                          {repo.last_change && (
                            <div className="flex items-center gap-2">
                              <Clock className="w-4 h-4" />
                              <span>Last: {formatTimestamp(repo.last_change)}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        {repo.is_watching ? (
                          <button
                            onClick={() => stopWatching(repo.id)}
                            className="p-2 text-orange-600 hover:bg-orange-50 rounded-lg transition-colors"
                            title="Stop watching"
                          >
                            <Square className="w-5 h-5" />
                          </button>
                        ) : (
                          <button
                            onClick={() => startWatching(repo.id)}
                            className="p-2 text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                            title="Start watching"
                          >
                            <Play className="w-5 h-5" />
                          </button>
                        )}
                        <button
                          onClick={() => {
                            setSelectedRepo(repo.id);
                            loadChanges(repo.id);
                            setActiveTab('changes');
                          }}
                          className="px-3 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors text-sm font-medium"
                        >
                          View Changes
                        </button>
                        <button
                          onClick={() => deleteRepo(repo.id)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="Delete repository"
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'changes' && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-xl font-semibold text-slate-900">Live Changes</h2>
                {selectedRepo && (
                  <button
                    onClick={() => {
                      setSelectedRepo(null);
                      loadChanges();
                    }}
                    className="text-sm text-blue-600 hover:underline mt-1"
                  >
                    Show all repositories
                  </button>
                )}
              </div>
              <button
                onClick={() => loadChanges(selectedRepo)}
                className="flex items-center gap-2 px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
            </div>

            <div className="space-y-3 max-h-[600px] overflow-y-auto">
              {changes.length === 0 ? (
                <div className="bg-white rounded-xl p-12 text-center border border-slate-200">
                  <Code className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-slate-900 mb-2">No changes yet</h3>
                  <p className="text-slate-500">Changes will appear here in real-time</p>
                </div>
              ) : (
                changes.map((change, idx) => (
                  <div
                    key={change.id || idx}
                    className="bg-white rounded-lg p-4 border border-slate-200 hover:border-blue-300 transition-all"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${getChangeTypeColor(change.change_type)}`}>
                            {change.change_type.toUpperCase()}
                          </span>
                          <span className="text-sm font-medium text-slate-700">{change.repository_name}</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-slate-600 mb-2">
                          <FileText className="w-4 h-4" />
                          <code className="font-mono text-slate-900">{change.relative_path}</code>
                          <span className="text-slate-400">•</span>
                          <span>{change.file_extension || 'no ext'}</span>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-slate-500">
                          <div className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {change.author}
                          </div>
                          <div className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {formatTimestamp(change.timestamp)}
                          </div>
                          {(change.lines_added > 0 || change.lines_removed > 0) && (
                            <>
                              <span className="text-green-600">+{change.lines_added}</span>
                              <span className="text-red-600">-{change.lines_removed}</span>
                            </>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        {change.sent_to_ai ? (
                          <CheckCircle className="w-5 h-5 text-green-600" title="Sent to AI" />
                        ) : (
                          <AlertCircle className="w-5 h-5 text-orange-600" title="Pending AI processing" />
                        )}
                      </div>
                    </div>

                    {change.git_diff && (
                      <details className="mt-3">
                        <summary className="cursor-pointer text-sm font-medium text-blue-600 hover:text-blue-700">
                          View diff
                        </summary>
                        <pre className="mt-2 p-3 bg-slate-50 rounded text-xs overflow-x-auto font-mono text-slate-700 border border-slate-200 max-h-96">
                          {change.git_diff}
                        </pre>
                      </details>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {activeTab === 'statistics' && stats && (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold text-slate-900">Statistics</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white rounded-xl p-6 border border-slate-200">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                    <Folder className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Total Repositories</p>
                    <p className="text-2xl font-bold text-slate-900">{stats.watcher_statistics.total_repositories}</p>
                  </div>
                </div>
                <p className="text-sm text-slate-600">
                  {stats.watcher_statistics.currently_watching} actively watching
                </p>
              </div>

              <div className="bg-white rounded-xl p-6 border border-slate-200">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                    <FileText className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Total Changes</p>
                    <p className="text-2xl font-bold text-slate-900">{stats.change_statistics.total_changes}</p>
                  </div>
                </div>
                <p className="text-sm text-slate-600">
                  {stats.change_statistics.recent_activity.last_24h} in last 24h
                </p>
              </div>

              <div className="bg-white rounded-xl p-6 border border-slate-200">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                    <Database className="w-5 h-5 text-purple-600" />
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">AI Success Rate</p>
                    <p className="text-2xl font-bold text-slate-900">
                      {Math.round(stats.change_statistics.success_rate)}%
                    </p>
                  </div>
                </div>
                <p className="text-sm text-slate-600">
                  {stats.change_statistics.sent_to_ai} / {stats.change_statistics.total_changes} sent
                </p>
              </div>
            </div>

            <div className="bg-white rounded-xl p-6 border border-slate-200">
              <h3 className="text-lg font-semibold text-slate-900 mb-4">Changes by Type</h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center">
                  <div className="text-3xl font-bold text-green-600 mb-1">
                    {stats.change_statistics.by_type.created}
                  </div>
                  <div className="text-sm text-slate-600">Created</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-blue-600 mb-1">
                    {stats.change_statistics.by_type.modified}
                  </div>
                  <div className="text-sm text-slate-600">Modified</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-red-600 mb-1">
                    {stats.change_statistics.by_type.deleted}
                  </div>
                  <div className="text-sm text-slate-600">Deleted</div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl p-6 border border-slate-200">
              <h3 className="text-lg font-semibold text-slate-900 mb-4">System Status</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-600">AI Backend</span>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                    stats.ai_backend_health.ai_backend_status === 'healthy'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  }`}>
                    {stats.ai_backend_health.ai_backend_status}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-600">WebSocket</span>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                    wsConnected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                  }`}>
                    {wsConnected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-600">Uptime</span>
                  <span className="text-sm font-medium text-slate-900">{stats.service_uptime}</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {showAddRepo && <AddRepoModal onClose={() => setShowAddRepo(false)} onAdd={(name, path) => {
        fetch(`${API_URL}/repos`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, path })
        }).then(response => {
          if (response.ok) {
            loadRepositories();
            setShowAddRepo(false);
          } else {
            response.json().then(error => alert(`Error: ${error.detail}`));
          }
        }).catch(error => {
          console.error('Error adding repository:', error);
          alert('Failed to add repository');
        });
      }} />}
    </div>
  );
}

function AddRepoModal({ onClose, onAdd }) {
  const [name, setName] = useState('');
  const [path, setPath] = useState('');

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
        <h2 className="text-xl font-semibold text-slate-900 mb-4">Add Repository</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Repository Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="my-project"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Repository Path
            </label>
            <input
              type="text"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
              placeholder="/path/to/repository"
            />
            <p className="text-xs text-slate-500 mt-1">
              Full path to the git repository directory
            </p>
          </div>
          <div className="flex gap-3 justify-end pt-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => {
                if (name && path) {
                  onAdd(name, path);
                }
              }}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Add Repository
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}