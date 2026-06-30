import { Suspense } from 'react';
import SearchClient from './client';

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-5xl mx-auto px-4 py-16 text-center">
          <div className="inline-block w-10 h-10 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin mb-4" />
          <p className="text-gray-500">Đang tải...</p>
        </div>
      }
    >
      <SearchClient />
    </Suspense>
  );
}
