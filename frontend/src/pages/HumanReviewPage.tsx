import React, { useState, useMemo } from 'react'
import { ShieldCheck, AlertCircle } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { apiClient, ApiClientError } from '../api/client'
import type { ReviewQueueResponse, InvestigationResponse, ReviewResponse, ReviewSubmissionRequest } from '../api/types'
import { EpistemicBadge } from '../components/epistemic/EpistemicBadge'
import { ReviewQueueList } from '../components/review/ReviewQueueList'
import { ReviewWorkspace } from '../components/review/ReviewWorkspace'
import { ErrorState } from '../components/common/ErrorState'
import { useIncidentContextStore } from '../store/incidentContextStore'

export const HumanReviewPage: React.FC = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { selectedIncidentId, setSelectedIncidentId } = useIncidentContextStore()

  const [selectedRecId, setSelectedRecId] = useState<string | null>(null)
  const [lastReceipt, setLastReceipt] = useState<ReviewResponse | null>(null)
  const [submissionError, setSubmissionError] = useState<string | null>(null)

  // 1. Fetch Review Queue from actual backend endpoint
  const {
    data: queueData,
    isLoading: isLoadingQueue,
    isError: isQueueError,
    error: queueError,
    refetch: refetchQueue,
  } = useQuery<ReviewQueueResponse, ApiClientError>({
    queryKey: ['review-queue'],
    queryFn: () => apiClient.get<ReviewQueueResponse>('/api/v1/incidents/reviews/queue'),
    staleTime: 10000,
  })

  const queueItems = useMemo(() => queueData?.items || [], [queueData])

  // Derive the active selected item cleanly without setState in useEffect
  const selectedItem = useMemo(() => {
    if (queueItems.length === 0) return null
    if (selectedRecId) {
      const match = queueItems.find((i) => i.recommendation_id === selectedRecId)
      if (match) return match
    }
    if (selectedIncidentId) {
      const match = queueItems.find((i) => i.incident_id === selectedIncidentId)
      if (match) return match
    }
    return queueItems[0]
  }, [queueItems, selectedRecId, selectedIncidentId])

  // 2. Fetch full Investigation context for selected item
  const {
    data: investigationData,
    isLoading: isLoadingInvestigation,
  } = useQuery<InvestigationResponse, ApiClientError>({
    queryKey: ['investigation', selectedItem?.incident_id],
    queryFn: () =>
      apiClient.get<InvestigationResponse>(
        `/api/v1/incidents/${selectedItem!.incident_id}/investigation`
      ),
    enabled: !!selectedItem?.incident_id && selectedItem.incident_id !== 'UNKNOWN',
    retry: 1,
  })

  // 3. Submit Review Mutation (POST /api/v1/incidents/{incident_id}/reviews)
  const reviewMutation = useMutation<
    ReviewResponse,
    ApiClientError,
    { decision: 'APPROVED' | 'REJECTED'; notes: string }
  >({
    mutationFn: async ({ decision, notes }) => {
      if (!selectedItem) throw new Error('No recommendation selected')
      setSubmissionError(null)

      const body: ReviewSubmissionRequest = {
        recommendation_id: selectedItem.recommendation_id,
        decision,
        review_notes: notes,
      }

      return apiClient.post<ReviewResponse>(
        `/api/v1/incidents/${selectedItem.incident_id}/reviews`,
        body
      )
    },
    onSuccess: (receipt) => {
      setLastReceipt(receipt)
      setSubmissionError(null)

      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: ['review-queue'] })
      if (selectedItem?.incident_id) {
        queryClient.invalidateQueries({
          queryKey: ['investigation', selectedItem.incident_id],
        })
        queryClient.invalidateQueries({
          queryKey: ['incident-reviews', selectedItem.incident_id],
        })
      }
      queryClient.invalidateQueries({ queryKey: ['audit-records'] })
    },
    onError: (err) => {
      if (err.status === 409) {
        setSubmissionError(
          'Conflict (409): Recommendation is already in a terminal state. Replay and duplicate sign-offs are strictly blocked.'
        )
      } else if (err.status === 403) {
        setSubmissionError(
          'Forbidden (403): You lack operational review privileges. Service accounts and viewer roles are prohibited from signing reviews.'
        )
      } else {
        setSubmissionError(err.message || 'Review submission failed.')
      }
    },
  })

  const handleSubmitReview = async (decision: 'APPROVED' | 'REJECTED', notes: string) => {
    await reviewMutation.mutateAsync({ decision, notes })
  }

  const handleOpenInvestigation = (incidentId: string) => {
    setSelectedIncidentId(incidentId)
    navigate('/investigation')
  }

  return (
    <div className="space-y-6">
      {/* 1. Governance & Epistemic Boundary Notice Banner */}
      <div className="rounded-sm bg-[var(--bg-surface)] border border-[var(--border-subtle)] p-4 flex items-start gap-3.5 transition-colors">
        <ShieldCheck className="w-5 h-5 text-[var(--text-primary)] shrink-0 mt-0.5" />
        <div className="space-y-1 text-xs">
          <div className="font-bold text-sm text-[var(--text-primary)] flex items-center gap-2">
            <span>Human Review Gateway & Decision Notarization</span>
            <EpistemicBadge category="HUMAN_APPROVED_DECISION" size="sm" />
          </div>
          <p className="text-[var(--text-muted)] leading-relaxed">
            Every diagnostic check requires authenticated human operator review before physical execution by NOC field engineers. PIIS remains strictly an analytical and advisory decision-support platform. Submitting an approval cryptographically signs the recommendation into the RFC 8785 audit ledger and does <strong>not</strong> trigger automated production changes, ticket closure, or CLI command execution.
          </p>
        </div>
      </div>

      {/* 2. Main Workspace Layout */}
      {isQueueError ? (
        <ErrorState
          icon={AlertCircle}
          title="Failed to Load Review Queue"
          message={
            queueError?.message ||
            'An error occurred while querying the human review queue. Please verify backend service health.'
          }
          onRetry={() => refetchQueue()}
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Review Queue (5 cols) */}
          <div className="lg:col-span-5">
            <div className="rounded-sm border bg-[var(--bg-surface)] border-[var(--border-subtle)] p-4 transition-colors">
              <ReviewQueueList
                items={queueItems}
                selectedItem={selectedItem}
                onSelectItem={(item) => {
                  setSelectedRecId(item.recommendation_id)
                  setSelectedIncidentId(item.incident_id)
                  setLastReceipt(null)
                  setSubmissionError(null)
                }}
                isLoading={isLoadingQueue}
                pendingCount={queueData?.pending_count || 0}
                approvedCount={queueData?.approved_count || 0}
                rejectedCount={queueData?.rejected_count || 0}
                onRefresh={() => refetchQueue()}
              />
            </div>
          </div>

          {/* Right Column: Review Workspace (7 cols) */}
          <div className="lg:col-span-7">
            <ReviewWorkspace
              selectedItem={selectedItem}
              investigation={investigationData}
              isLoadingInvestigation={isLoadingInvestigation}
              onSubmitReview={handleSubmitReview}
              isSubmitting={reviewMutation.isPending}
              lastReceipt={lastReceipt}
              onDismissReceipt={() => setLastReceipt(null)}
              onOpenInvestigation={handleOpenInvestigation}
              error={submissionError}
            />
          </div>
        </div>
      )}
    </div>
  )
}
