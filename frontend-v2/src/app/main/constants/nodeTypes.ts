/**
 * Node type configurations
 */

import { Bot, Mail, Clock, Layers } from "lucide-react"
import type { NodeTypeConfig } from "../types"

export const NODE_TYPE_CONFIG: NodeTypeConfig[] = [
  { value: "claude_code", label: "Claude Code", icon: Bot, color: "cyan" },
  { value: "email", label: "Email", icon: Mail, color: "blue" },
  { value: "scheduler", label: "Scheduler", icon: Clock, color: "purple" },
  { value: "aggregator", label: "Aggregator", icon: Layers, color: "emerald" },
]
