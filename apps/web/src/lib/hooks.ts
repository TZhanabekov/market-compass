/**
 * React Query hooks for API data fetching
 */

import { useQuery } from '@tanstack/react-query';
import { fetchHomeData, type HomeQueryParams } from './api';

/**
 * Hook to fetch home page data
 */
export function useHomeData(params: HomeQueryParams = {}) {
  return useQuery({
    queryKey: ['home', params],
    queryFn: () => fetchHomeData(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
  });
}
