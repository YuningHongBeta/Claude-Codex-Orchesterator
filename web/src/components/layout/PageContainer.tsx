import type { ReactNode } from 'react';

interface PageContainerProps {
  children: ReactNode;
}

export function PageContainer({ children }: PageContainerProps) {
  return (
    <main className="flex-1 overflow-auto pb-20">
      <div className="max-w-4xl mx-auto px-4 py-6">
        {children}
      </div>
    </main>
  );
}
