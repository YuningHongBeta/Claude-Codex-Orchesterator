import { useState, useEffect } from 'react';
import { FileText, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import { fetchLogs, fetchLogContent } from '../../services/api';
import type { LogFile } from '../../types';

interface LogViewerProps {
  jobId: string;
}

const stageLabels: Record<string, string> = {
  rewriter: '指揮者',
  conductor: '指揮者',
  mix: '統合',
};

function getStageLabel(stage: string): string {
  if (stage.startsWith('performer_')) {
    const num = stage.replace('performer_', '');
    return `演奏者 ${num}`;
  }
  if (stage.startsWith('concertmaster_')) {
    const num = stage.replace('concertmaster_', '');
    return `コンマス ${num}`;
  }
  return stageLabels[stage] || stage;
}

export function LogViewer({ jobId }: LogViewerProps) {
  const [logs, setLogs] = useState<LogFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedLog, setExpandedLog] = useState<string | null>(null);
  const [logContent, setLogContent] = useState<Record<string, string>>({});
  const [loadingContent, setLoadingContent] = useState<string | null>(null);

  useEffect(() => {
    const saved = sessionStorage.getItem(`orchestrator:logExpanded:${jobId}`);
    setExpandedLog(saved || null);
  }, [jobId]);

  useEffect(() => {
    const key = `orchestrator:logExpanded:${jobId}`;
    if (expandedLog) {
      sessionStorage.setItem(key, expandedLog);
    } else {
      sessionStorage.removeItem(key);
    }
  }, [expandedLog, jobId]);

  useEffect(() => {
    async function loadLogs() {
      setLoading(true);
      const data = await fetchLogs(jobId);
      setLogs(data);
      setLoading(false);
    }
    loadLogs();
  }, [jobId]);

  const handleToggle = async (filename: string) => {
    if (expandedLog === filename) {
      setExpandedLog(null);
      return;
    }

    setExpandedLog(filename);

    if (!logContent[filename]) {
      setLoadingContent(filename);
      try {
        const content = await fetchLogContent(jobId, filename);
        setLogContent((prev) => ({ ...prev, [filename]: content }));
      } catch {
        setLogContent((prev) => ({ ...prev, [filename]: 'ログの読み込みに失敗しました' }));
      } finally {
        setLoadingContent(null);
      }
    }
  };

  // Group logs by stage
  const groupedLogs = logs.reduce(
    (acc, log) => {
      if (!acc[log.stage]) acc[log.stage] = [];
      acc[log.stage].push(log);
      return acc;
    },
    {} as Record<string, LogFile[]>
  );

  useEffect(() => {
    if (!expandedLog) return;
    const exists = logs.some((log) => log.filename === expandedLog);
    if (!exists) {
      setExpandedLog(null);
    }
  }, [logs, expandedLog]);

  const stages = Object.keys(groupedLogs).sort((a, b) => {
    // Sort: conductor first, then performers in order, then mix
    if (a === 'conductor') return -1;
    if (b === 'conductor') return 1;
    if (a === 'mix') return 1;
    if (b === 'mix') return -1;
    return a.localeCompare(b, undefined, { numeric: true });
  });

  if (loading) {
    return (
      <div className="glass-light rounded-2xl p-6">
        <div className="flex items-center gap-2 text-slate-400">
          <Loader2 size={20} className="animate-spin" />
          <span>ログを読み込み中...</span>
        </div>
      </div>
    );
  }

  if (logs.length === 0) {
    return (
      <div className="glass-light rounded-2xl p-6 text-center">
        <FileText size={32} className="mx-auto mb-2 text-slate-600" />
        <p className="text-slate-500">ログファイルがありません</p>
      </div>
    );
  }

  return (
    <div className="glass-light rounded-2xl overflow-hidden">
      <div className="p-4 border-b border-slate-700/50">
        <div className="flex items-center gap-2 text-slate-300">
          <FileText size={20} />
          <h3 className="font-semibold">ログ</h3>
          <span className="text-xs text-slate-500">({logs.length}ファイル)</span>
        </div>
      </div>

      <div className="divide-y divide-slate-700/30">
        {stages.map((stage) => (
          <div key={stage} className="p-3">
            <div className="text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">
              {getStageLabel(stage)}
            </div>
            <div className="space-y-1">
              {groupedLogs[stage].map((log) => (
                <div key={log.filename}>
                  <button
                    onClick={() => handleToggle(log.filename)}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-700/30 transition-colors text-left"
                  >
                    {expandedLog === log.filename ? (
                      <ChevronDown size={16} className="text-slate-500" />
                    ) : (
                      <ChevronRight size={16} className="text-slate-500" />
                    )}
                    <span
                      className={`text-sm ${log.type === 'stderr' ? 'text-yellow-400' : 'text-slate-300'}`}
                    >
                      {log.type === 'stdout' ? '標準出力' : '標準エラー'}
                    </span>
                    <span className="text-xs text-slate-600 ml-auto">
                      {(log.size / 1024).toFixed(1)} KB
                    </span>
                  </button>
                  {expandedLog === log.filename && (
                    <div className="mt-2 mx-3 mb-2">
                      {loadingContent === log.filename ? (
                        <div className="flex items-center gap-2 text-slate-400 text-sm p-4">
                          <Loader2 size={16} className="animate-spin" />
                          <span>読み込み中...</span>
                        </div>
                      ) : (
                        <pre className="text-xs text-slate-300 bg-slate-900/50 rounded-lg p-4 overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap font-mono">
                          {logContent[log.filename] || ''}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
