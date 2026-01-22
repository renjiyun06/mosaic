/**
 * Subscription Management Panel - Manages subscriptions for a specific connection
 */

import { motion, AnimatePresence } from "framer-motion"
import { Bell, X, Plus, Edit, Trash2, ArrowRight } from "lucide-react"
import { EventType, type SubscriptionOut } from "@/lib/types"

interface SubscriptionManagementPanelProps {
  open: boolean
  onClose: () => void
  connectionId: number | null
  sourceNodeId: string
  targetNodeId: string
  subscriptions: SubscriptionOut[]
  onAddSubscription: () => void
  onEditSubscription: (subscription: SubscriptionOut) => void
  onDeleteSubscription: (subscription: SubscriptionOut) => void
}

// Event type labels
const EVENT_TYPE_LABELS: Record<EventType, string> = {
  [EventType.SESSION_START]: "Session Start",
  [EventType.SESSION_RESPONSE]: "Session Response",
  [EventType.USER_PROMPT_SUBMIT]: "User Prompt Submit",
  [EventType.PRE_TOOL_USE]: "Pre Tool Use",
  [EventType.POST_TOOL_USE]: "Post Tool Use",
  [EventType.SESSION_END]: "Session End",
  [EventType.NODE_MESSAGE]: "Node Message",
  [EventType.EVENT_BATCH]: "Event Batch",
  [EventType.SYSTEM_MESSAGE]: "System Message",
  [EventType.EMAIL_MESSAGE]: "Email Message",
  [EventType.SCHEDULER_MESSAGE]: "Scheduler Message",
  [EventType.REDDIT_SCRAPER_MESSAGE]: "Reddit Scraper",
  [EventType.USER_MESSAGE_EVENT]: "User Message Event",
}

// Event type colors (cyberpunk themed)
const EVENT_TYPE_COLORS: Record<EventType, string> = {
  [EventType.SESSION_START]: "from-emerald-500 to-green-600",
  [EventType.SESSION_RESPONSE]: "from-cyan-500 to-blue-600",
  [EventType.USER_PROMPT_SUBMIT]: "from-purple-500 to-pink-600",
  [EventType.PRE_TOOL_USE]: "from-amber-500 to-orange-600",
  [EventType.POST_TOOL_USE]: "from-amber-500 to-orange-600",
  [EventType.SESSION_END]: "from-red-500 to-rose-600",
  [EventType.NODE_MESSAGE]: "from-cyan-500 to-teal-600",
  [EventType.EVENT_BATCH]: "from-indigo-500 to-purple-600",
  [EventType.SYSTEM_MESSAGE]: "from-slate-500 to-gray-600",
  [EventType.EMAIL_MESSAGE]: "from-blue-500 to-cyan-600",
  [EventType.SCHEDULER_MESSAGE]: "from-violet-500 to-purple-600",
  [EventType.REDDIT_SCRAPER_MESSAGE]: "from-orange-500 to-red-600",
  [EventType.USER_MESSAGE_EVENT]: "from-purple-500 to-pink-600",
}

export function SubscriptionManagementPanel({
  open,
  onClose,
  connectionId,
  sourceNodeId,
  targetNodeId,
  subscriptions,
  onAddSubscription,
  onEditSubscription,
  onDeleteSubscription,
}: SubscriptionManagementPanelProps) {
  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-[100] bg-black/40 backdrop-blur-sm"
          />

          {/* Panel */}
          <motion.div
            initial={{ x: 400, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 400, opacity: 0 }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 z-[101] h-screen w-[480px] border-l border-cyan-400/30 bg-gradient-to-br from-slate-950/95 to-slate-900/95 shadow-[0_0_50px_rgba(34,211,238,0.3)] backdrop-blur-2xl"
          >
            {/* Neon left accent */}
            <div className="absolute inset-y-0 left-0 w-px bg-gradient-to-b from-transparent via-cyan-400 to-transparent" />

            {/* Header */}
            <div className="border-b border-white/10 p-6">
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-[0_0_20px_rgba(34,211,238,0.4)]">
                    <Bell className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <h2 className="font-mono text-lg font-bold text-white">
                      Subscriptions
                    </h2>
                    <p className="text-xs text-slate-400">
                      {subscriptions.length} active
                    </p>
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="group rounded-xl border border-white/10 bg-white/5 p-2 transition-all hover:border-cyan-400/50 hover:bg-cyan-500/20"
                >
                  <X className="h-5 w-5 text-slate-400 transition-colors group-hover:text-cyan-300" />
                </button>
              </div>

              {/* Connection Info */}
              <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-slate-800/50 p-3">
                <span className="flex-1 truncate font-mono text-sm font-medium text-cyan-300">
                  {sourceNodeId}
                </span>
                <ArrowRight className="h-4 w-4 shrink-0 text-slate-400" />
                <span className="flex-1 truncate font-mono text-sm font-medium text-cyan-300">
                  {targetNodeId}
                </span>
              </div>
            </div>

            {/* Subscriptions List */}
            <div className="h-[calc(100vh-200px)] overflow-y-auto p-6">
              <div className="mb-4">
                <button
                  onClick={onAddSubscription}
                  className="w-full rounded-lg border border-cyan-400/30 bg-cyan-500/20 py-2.5 text-sm font-medium text-cyan-300 transition-all hover:border-cyan-400/50 hover:bg-cyan-500/30 hover:shadow-[0_0_15px_rgba(34,211,238,0.3)]"
                >
                  <Plus className="mr-2 inline-block h-4 w-4" />
                  Add Subscription
                </button>
              </div>

              <div className="space-y-3">
                {subscriptions.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-20 text-center">
                    <Bell className="mb-4 h-12 w-12 text-slate-500" />
                    <p className="text-sm text-slate-400">
                      No subscriptions yet
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Add subscriptions to forward events
                    </p>
                  </div>
                ) : (
                  subscriptions.map((subscription, i) => (
                    <motion.div
                      key={subscription.id}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      className="group rounded-xl border border-white/10 bg-white/5 p-4 transition-all hover:border-cyan-400/30 hover:bg-white/10"
                    >
                      {/* Event Type Badge */}
                      <div className="mb-3 flex items-center justify-between">
                        <div
                          className={`inline-flex items-center gap-2 rounded-lg bg-gradient-to-r ${
                            EVENT_TYPE_COLORS[subscription.event_type]
                          } px-3 py-1.5 text-xs font-semibold text-white shadow-lg`}
                        >
                          <Bell className="h-3 w-3" />
                          {EVENT_TYPE_LABELS[subscription.event_type]}
                        </div>
                      </div>

                      {/* Description */}
                      {subscription.description && (
                        <p className="mb-3 text-xs text-slate-400">
                          {subscription.description}
                        </p>
                      )}

                      {/* Created Date */}
                      <div className="mb-3 text-xs text-slate-500">
                        Created {new Date(subscription.created_at).toLocaleDateString()}
                      </div>

                      {/* Actions */}
                      <div className="flex gap-2">
                        <button
                          onClick={() => onEditSubscription(subscription)}
                          className="flex-1 rounded-lg border border-white/10 bg-white/5 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-cyan-400/30 hover:bg-cyan-500/20 hover:text-cyan-300"
                        >
                          <Edit className="mr-1.5 inline-block h-3 w-3" />
                          Edit
                        </button>
                        <button
                          onClick={() => onDeleteSubscription(subscription)}
                          className="flex-1 rounded-lg border border-red-400/20 bg-red-500/10 py-1.5 text-xs font-medium text-red-400 transition-colors hover:border-red-400/40 hover:bg-red-500/20 hover:text-red-300"
                        >
                          <Trash2 className="mr-1.5 inline-block h-3 w-3" />
                          Delete
                        </button>
                      </div>
                    </motion.div>
                  ))
                )}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
