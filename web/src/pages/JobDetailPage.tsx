import { useParams } from 'react-router-dom';
import { PageContainer } from '../components/layout';
import { JobDetail } from '../components/jobs';
import { useJobDetail } from '../hooks/useJobs';

export function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { job, loading, error, lastUpdatedAt } = useJobDetail(id || '');

  return (
    <PageContainer>
      <JobDetail job={job} loading={loading} error={error} lastUpdatedAt={lastUpdatedAt} />
    </PageContainer>
  );
}
