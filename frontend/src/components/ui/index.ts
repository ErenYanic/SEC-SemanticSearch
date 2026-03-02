/**
 * Barrel export for shared UI components.
 *
 * Usage:
 *   import { Button, Badge, Modal, useToast } from "@/components/ui";
 *
 * Mirrors the `components/layout/index.ts` pattern.
 */

export { Button, type ButtonProps } from "./Button";
export { Spinner, FullPageSpinner } from "./Spinner";
export { Badge, taskStateToBadgeVariant, type BadgeProps } from "./Badge";
export { SimilarityBadge } from "./SimilarityBadge";
export { Modal, type ModalProps } from "./Modal";
export { MetricCard, type MetricCardProps } from "./MetricCard";
export { EmptyState, type EmptyStateProps } from "./EmptyState";
export { ToastProvider, useToast } from "./Toast";
export { Skeleton, SkeletonText } from "./Skeleton";