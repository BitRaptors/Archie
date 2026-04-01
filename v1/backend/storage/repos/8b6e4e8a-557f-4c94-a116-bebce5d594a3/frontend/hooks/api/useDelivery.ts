import { useMutation } from '@tanstack/react-query'
import { deliveryService } from '@/services/delivery'
import type { DeliveryRequest } from '@/services/delivery'

/** Mutation to push architecture outputs to a target repo. */
export function useDeliveryApply() {
  return useMutation({
    mutationFn: ({ req, token }: { req: DeliveryRequest; token?: string }) =>
      deliveryService.apply(req, token),
  })
}

/** Mutation for preview (on-demand, not cached). */
export function useDeliveryPreview() {
  return useMutation({
    mutationFn: ({
      sourceRepoId,
      outputs,
    }: {
      sourceRepoId: string
      outputs: string[]
    }) => deliveryService.preview(sourceRepoId, outputs),
  })
}
