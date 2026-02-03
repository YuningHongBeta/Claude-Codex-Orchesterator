import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchJobs, fetchJob, createJob } from '../services/api';
import { REFRESH_INTERVAL } from '../constants';
import type { Job } from '../types';

export function useJobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const initialLoadedRef = useRef(false);

  const sortJobs = useCallback((list: Job[]) => {
    return [...list].sort((a, b) => {
      const aTime = a.updated_at || a.started_at || '';
      const bTime = b.updated_at || b.started_at || '';
      if (aTime !== bTime) {
        return bTime.localeCompare(aTime);
      }
      return a.id.localeCompare(b.id);
    });
  }, []);

  const isSameJobs = useCallback((prev: Job[], next: Job[]) => {
    if (prev.length !== next.length) return false;
    for (let i = 0; i < prev.length; i += 1) {
      const a = prev[i];
      const b = next[i];
      if (!a || !b) return false;
      if (a.id !== b.id) return false;
      if (
        a.stage !== b.stage ||
        a.progress !== b.progress ||
        a.running !== b.running ||
        a.error !== b.error
      ) {
        return false;
      }
    }
    return true;
  }, []);

  const refresh = useCallback(async () => {
    try {
      if (!initialLoadedRef.current) {
        setLoading(true);
      }
      const data = sortJobs(await fetchJobs());
      setJobs((prev) => {
        const same = isSameJobs(prev, data);
        if (!same) {
          setLastUpdatedAt(new Date().toISOString());
        }
        return same ? prev : data;
      });
      setError(null);
    } catch (err) {
      setError('ジョブ一覧の取得に失敗しました');
    } finally {
      if (!initialLoadedRef.current) {
        setLoading(false);
        initialLoadedRef.current = true;
      }
    }
  }, [isSameJobs, sortJobs]);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [refresh]);

  const runningCount = jobs.filter((job) => job.running).length;
  const completedCount = jobs.filter((job) => job.stage === 'done').length;
  const errorCount = jobs.filter((job) => job.stage === 'error').length;

  return {
    jobs,
    loading,
    error,
    refresh,
    runningCount,
    completedCount,
    errorCount,
    totalCount: jobs.length,
    lastUpdatedAt,
  };
}

export function useJobDetail(jobId: string | null) {
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const initialLoadedRef = useRef(false);

  const isSameJob = useCallback((a: Job | null, b: Job | null) => {
    if (!a || !b) return false;
    return (
      a.id === b.id &&
      a.stage === b.stage &&
      a.progress === b.progress &&
      a.running === b.running &&
      a.error === b.error &&
      a.final_text === b.final_text &&
      a.performer_index === b.performer_index &&
      a.performer_total === b.performer_total &&
      a.performer_name === b.performer_name
    );
  }, []);

  const loadJob = useCallback(async (id: string) => {
    if (!initialLoadedRef.current) {
      setLoading(true);
    }
    setError(null);
    try {
      const data = await fetchJob(id, true);
      setJob((prev) => {
        const same = isSameJob(prev, data);
        if (!same) {
          setLastUpdatedAt(new Date().toISOString());
        }
        return same ? prev : data;
      });
    } catch (err) {
      setError('ジョブの詳細取得に失敗しました');
      if (!initialLoadedRef.current) {
        setJob(null);
      }
    } finally {
      if (!initialLoadedRef.current) {
        setLoading(false);
        initialLoadedRef.current = true;
      }
    }
  }, [isSameJob]);

  useEffect(() => {
    if (jobId) {
      initialLoadedRef.current = false;
      loadJob(jobId);
      const interval = setInterval(() => loadJob(jobId), REFRESH_INTERVAL);
      return () => clearInterval(interval);
    } else {
      setJob(null);
    }
  }, [jobId, loadJob]);

  return { job, loading, error, refresh: () => jobId && loadJob(jobId), lastUpdatedAt };
}

export function useCreateJob() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async (task: string): Promise<Job | null> => {
    setLoading(true);
    setError(null);
    try {
      const job = await createJob(task);
      return job;
    } catch (err) {
      setError('ジョブの投入に失敗しました');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { submit, loading, error };
}
