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
