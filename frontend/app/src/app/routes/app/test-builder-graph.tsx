import { type ComponentType, useEffect, useMemo, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { useMutation, useQuery } from '@tanstack/react-query'
import { RoleGuard } from '@/app/components/RoleGuard'
import { QuestionPayloadEditor } from '@/app/components/QuestionPayloadEditor'
import { apiFetch, queryClient } from '@/api/client'

import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react'

import '@xyflow/react/dist/style.css'

type QuestionMeta = {
  id: number
  index: number
  key?: string | null
  title: string
  prompt: string
  kind: 'choice' | 'text'
  options: string[]
  options_count: number
  correct_label: string | null
  is_active: boolean
  updated_at: string | null
}

type QuestionGroup = {
  test_id: string
  title: string
  questions: QuestionMeta[]
}

type GraphPayload = {
  ok: boolean
  test_id: string
  graph: { schema: string; nodes: PersistedFlowNode[]; edges: PersistedFlowEdge[] }
  updated_at: string | null
}

type QuestionDetailPayload = {
  id: number
  title: string
  test_id: string
  question_index: number
  payload: string
  is_active: boolean
}

type GraphPreviewQuestion = {
  question_id: number | null
  key: string
  prompt: string
  kind: 'choice' | 'text'
  options: string[]
  placeholder?: string | null
  helper?: string | null
  is_active: boolean
}

type GraphPreviewStep = {
  question: GraphPreviewQuestion
  answer: string
  status: 'ok' | 'invalid' | 'reject'
  reaction: {
    message?: string
    hints?: string[]
    reason?: string | null
    template_key?: string | null
    template_text?: string | null
    edge_label?: string | null
  }
  inserted_followups: string[]
}

type GraphPreviewPayload = {
  ok: boolean
  test_id: string
  base_count: number
  sequence_count: number
  steps: GraphPreviewStep[]
  next_question: GraphPreviewQuestion | null
  halted: boolean
  halt_reason: string | null
  done: boolean
}

type BranchMatchMode = 'always' | 'equals' | 'contains'
type BranchAction = 'next' | 'reject'

type BranchEdgeData = {
  when?: string
  match: BranchMatchMode
  fallback: boolean
  action: BranchAction
  reason?: string
  template_key?: string
  priority: number
  label?: string
}

type FlowNodeData = {
  label?: string
  question_id?: number | string | null
  key?: string | null
  title?: string
  prompt?: string
  options?: string[]
  is_active?: boolean
  placeholder?: string | null
}

type FlowNode = Node<FlowNodeData>
type FlowEdge = Edge<BranchEdgeData>

type PersistedFlowNode = Pick<FlowNode, 'id' | 'type' | 'position' | 'data'>
type PersistedFlowEdge = Pick<
  FlowEdge,
  'id' | 'source' | 'target' | 'sourceHandle' | 'targetHandle' | 'data' | 'label'
>

function readQuestionId(data: unknown): number | null {
  if (!data || typeof data !== 'object') return null
  const raw = (data as Record<string, unknown>).question_id
  if (typeof raw === 'number' && !Number.isNaN(raw)) return raw
  if (typeof raw === 'string' && raw.trim()) {
    const parsed = Number(raw)
    return Number.isNaN(parsed) ? null : parsed
  }
  return null
}

function readQuestionKey(data: unknown): string | null {
  if (!data || typeof data !== 'object') return null
  const raw = (data as Record<string, unknown>).key
  if (typeof raw !== 'string') return null
  const cleaned = raw.trim()
  return cleaned || null
}

function normalizeEdgeData(data: unknown): BranchEdgeData {
  const raw = data && typeof data === 'object' ? (data as Record<string, unknown>) : {}

  const matchRaw = String(raw.match || '').trim().toLowerCase()
  const match: BranchMatchMode = matchRaw === 'equals' || matchRaw === 'contains' || matchRaw === 'always'
    ? (matchRaw as BranchMatchMode)
    : 'always'

  const actionRaw = String(raw.action || '').trim().toLowerCase()
  const action: BranchAction = actionRaw === 'reject' ? 'reject' : 'next'

  const whenRaw = typeof raw.when === 'string' ? raw.when.trim() : ''
  const labelRaw = typeof raw.label === 'string' ? raw.label.trim() : ''
  const reasonRaw = typeof raw.reason === 'string' ? raw.reason.trim() : ''
  const templateKeyRaw = typeof raw.template_key === 'string' ? raw.template_key.trim() : ''

  let priority = 0
  if (typeof raw.priority === 'number' && Number.isFinite(raw.priority)) {
    priority = Math.trunc(raw.priority)
  } else if (typeof raw.priority === 'string' && raw.priority.trim()) {
    const parsed = Number(raw.priority)
    priority = Number.isFinite(parsed) ? Math.trunc(parsed) : 0
  }

  return {
    when: whenRaw || undefined,
    match,
    fallback: Boolean(raw.fallback),
    action,
    reason: reasonRaw || undefined,
    template_key: templateKeyRaw || undefined,
    priority,
    label: labelRaw || undefined,
  }
}

function edgeLabel(data: BranchEdgeData): string {
  if (data.label && data.label.trim()) return data.label.trim()

  const condition = data.match === 'always'
    ? 'else'
    : data.when
      ? data.match === 'contains'
        ? `contains: ${data.when}`
        : `if = ${data.when}`
      : 'if'

  if (data.action === 'reject') return `${condition} -> reject`
  return condition
}

function stripNode(node: FlowNode): PersistedFlowNode {
  return {
    id: node.id,
    type: node.type,
    position: node.position,
    data: node.data,
  }
}

function stripEdge(edge: FlowEdge): PersistedFlowEdge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle,
    targetHandle: edge.targetHandle,
    data: edge.data,
    label: edge.label,
  }
}

function readNodeLabel(data: FlowNodeData | undefined, fallback: string): string {
  return typeof data?.label === 'string' && data.label.trim() ? data.label : fallback
}

function formatPrompt(text: string) {
  const clean = String(text || '').trim()
  if (!clean) return '—'
  if (clean.length <= 160) return clean
  return `${clean.slice(0, 157)}...`
}

function StartNode(props: NodeProps<FlowNode>) {
  const label = readNodeLabel(props.data, 'Start')
  return (
    <div className={`rs-flow-node rs-flow-node--start${props.selected ? ' is-selected' : ''}`}>
      <div className="rs-flow-node__title">{label}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

function EndNode(props: NodeProps<FlowNode>) {
  const label = readNodeLabel(props.data, 'End')
  return (
    <div className={`rs-flow-node rs-flow-node--end${props.selected ? ' is-selected' : ''}`}>
      <Handle type="target" position={Position.Top} />
      <div className="rs-flow-node__title">{label}</div>
    </div>
  )
}

function QuestionNode(props: NodeProps<FlowNode>) {
  const data = props.data
  const qid = readQuestionId(data)
  const key = readQuestionKey(data)
  const title = typeof data?.title === 'string' && data.title.trim() ? data.title : 'Вопрос'
  const prompt = typeof data?.prompt === 'string' ? data.prompt : ''
  const isActive = data?.is_active !== false

  return (
    <div className={`rs-flow-node rs-flow-node--question${props.selected ? ' is-selected' : ''}${isActive ? '' : ' is-disabled'}`}>
      <Handle type="target" position={Position.Top} />
      <div className="rs-flow-node__title">{title}</div>
      <div className="rs-flow-node__meta">
        {key ? <><code>{key}</code> · </> : null}
        ID: <code>{qid ?? 'virtual'}</code>
        {!isActive ? ' · отключён' : ''}
      </div>
      {prompt ? <div className="rs-flow-node__meta">{prompt}</div> : null}
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

const nodeTypes: Record<string, ComponentType<NodeProps<FlowNode>>> = {
  start: StartNode,
  end: EndNode,
  question: QuestionNode,
}

function makeBranchEdge(
  source: string,
  target: string,
  dataPatch: Partial<BranchEdgeData>,
): FlowEdge {
  const data = normalizeEdgeData(dataPatch)
  const slug = `${data.when || data.match || 'edge'}-${data.action}-${Math.random().toString(36).slice(2, 7)}`
  return {
    id: `e_${source}_${target}_${slug}`,
    source,
    target,
    data,
    label: edgeLabel(data),
  }
}

export function TestBuilderGraphPage() {
  const questionsMeta = useQuery<QuestionGroup[]>({
    queryKey: ['questions-meta'],
    queryFn: () => apiFetch<QuestionGroup[]>('/questions'),
  })

  const groups = useMemo(() => questionsMeta.data || [], [questionsMeta.data])

  const [activeTest, setActiveTest] = useState<string>('')
  useEffect(() => {
    if (!activeTest && groups.length) setActiveTest(groups[0].test_id)
  }, [activeTest, groups])

  const activeGroup = useMemo(
    () => groups.find((g) => g.test_id === activeTest) || null,
    [groups, activeTest],
  )

  const questionById = useMemo(() => {
    const map = new Map<number, QuestionMeta>()
    ;(activeGroup?.questions || []).forEach((q) => map.set(q.id, q))
    return map
  }, [activeGroup])

  const graphQuery = useQuery({
    queryKey: ['test-builder-graph', activeTest],
    enabled: Boolean(activeTest),
    queryFn: async () => {
      const qs = new URLSearchParams({ test_id: activeTest })
      return apiFetch<GraphPayload>(`/test-builder/graph?${qs.toString()}`)
    },
  })

  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge>([])
  const [message, setMessage] = useState('')
  const [selectedQuestionId, setSelectedQuestionId] = useState<number | null>(null)
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null)

  useEffect(() => {
    const payload = graphQuery.data
    if (!payload?.graph) return

    const rawNodes = Array.isArray(payload.graph.nodes) ? payload.graph.nodes : []
    const rawEdges = Array.isArray(payload.graph.edges) ? payload.graph.edges : []

    const normalizedEdges = rawEdges.map((edge) => {
      const data = normalizeEdgeData(edge.data)
      return {
        ...edge,
        data,
        label: edge.label || edgeLabel(data),
      }
    })

    setNodes(rawNodes)
    setEdges(normalizedEdges)
    setSelectedQuestionId(null)
    setSelectedEdgeId(null)
    setMessage('')
  }, [graphQuery.data, setEdges, setNodes])

  useEffect(() => {
    if (!activeGroup) return
    setNodes((current) =>
      current.map((node) => {
        if (node.type !== 'question') return node
        const qid = readQuestionId(node.data)
        if (!qid) return node
        const meta = questionById.get(qid)
        if (!meta) return node

        const prevData = (node.data || {}) as Record<string, unknown>
        const existingKey = typeof prevData.key === 'string' ? prevData.key : undefined
        const nextData = {
          ...prevData,
          question_id: qid,
          key: meta.key || existingKey || `q_${qid}`,
          title: meta.title,
          prompt: meta.prompt,
          options: Array.isArray(meta.options) ? meta.options : [],
          is_active: meta.is_active,
        }

        const unchanged =
          prevData.key === nextData.key
          && prevData.title === nextData.title
          && prevData.prompt === nextData.prompt
          && prevData.is_active === nextData.is_active

        if (unchanged) return node
        return { ...node, data: nextData }
      }),
    )
  }, [activeGroup, questionById, setNodes])

  useEffect(() => {
    if (!selectedEdgeId) return
    if (!edges.find((edge) => edge.id === selectedEdgeId)) {
      setSelectedEdgeId(null)
    }
  }, [edges, selectedEdgeId])

  const graphForSave = useMemo(
    () => ({
      schema: 'xyflow_v1',
      nodes: nodes.map(stripNode),
      edges: edges.map(stripEdge),
    }),
    [nodes, edges],
  )

  const graphForPreviewHash = useMemo(() => JSON.stringify(graphForSave), [graphForSave])

  const applyMutation = useMutation({
    mutationFn: async () => {
      if (!activeTest) throw new Error('Тест не выбран')
      return apiFetch<{ ok: boolean; error?: string }>('/test-builder/graph/apply', {
        method: 'POST',
        body: JSON.stringify({ test_id: activeTest, graph: graphForSave }),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['questions'] })
      queryClient.invalidateQueries({ queryKey: ['questions-meta'] })
      queryClient.invalidateQueries({ queryKey: ['test-builder-graph', activeTest] })
      queryClient.invalidateQueries({ queryKey: ['test-builder-graph-preview', activeTest] })
      setMessage('Граф применён. Линейный порядок синхронизируется автоматически, ветки сохраняются в графе.')
      window.setTimeout(() => setMessage(''), 3000)
    },
    onError: (err) => {
      setMessage(err instanceof Error ? err.message : 'Не удалось применить граф')
    },
  })

  const onConnect = (connection: Connection) => {
    const data = normalizeEdgeData({ match: 'always', fallback: true, action: 'next' })
    setEdges((current) =>
      addEdge(
        {
          ...connection,
          id: `e_${connection.source}_${connection.target}_${Date.now()}`,
          data,
          label: edgeLabel(data),
        },
        current,
      ),
    )
  }

  const onNodeClick = (_event: unknown, node: FlowNode) => {
    setSelectedEdgeId(null)
    if (node.type !== 'question') {
      setSelectedQuestionId(null)
      return
    }

    const qid = readQuestionId(node.data)
    if (!qid) {
      setSelectedQuestionId(null)
      return
    }
    setSelectedQuestionId(qid)
  }

  const onEdgeClick = (_event: unknown, edge: FlowEdge) => {
    setSelectedQuestionId(null)
    setSelectedEdgeId(edge.id)
  }

  const selectedMeta = useMemo(() => {
    if (!selectedQuestionId) return null
    return questionById.get(selectedQuestionId) || null
  }, [selectedQuestionId, questionById])

  const selectedEdge = useMemo(() => {
    if (!selectedEdgeId) return null
    return edges.find((edge) => edge.id === selectedEdgeId) || null
  }, [edges, selectedEdgeId])

  const nodeLabelById = useMemo(() => {
      const map = new Map<string, string>()
    for (const node of nodes) {
      if (node.type === 'start' || node.type === 'end') {
        map.set(node.id, readNodeLabel(node.data, String(node.type || 'node')))
        continue
      }

      const data = (node.data || {}) as Record<string, unknown>
      const key = typeof data.key === 'string' ? data.key : ''
      const title = typeof data.title === 'string' ? data.title : 'Вопрос'
      map.set(node.id, key ? `${key}: ${title}` : title)
    }
    return map
  }, [nodes])

  const [editTitle, setEditTitle] = useState('')
  const [editPayload, setEditPayload] = useState('{}')
  const [editActive, setEditActive] = useState(true)
  const [payloadValid, setPayloadValid] = useState(false)

  const detailQuery = useQuery({
    queryKey: ['question-detail', selectedQuestionId],
    queryFn: () => apiFetch<QuestionDetailPayload>(`/questions/${selectedQuestionId}`),
    enabled: Boolean(selectedQuestionId),
  })

  useEffect(() => {
    const d = detailQuery.data
    if (!d) return
    setEditTitle(d.title || '')
    setEditPayload(d.payload || '{}')
    setEditActive(Boolean(d.is_active))
    setPayloadValid(true)
  }, [detailQuery.data])

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!selectedQuestionId) throw new Error('Выберите вопрос в графе')
      if (!activeTest) throw new Error('Тест не выбран')
      if (!selectedMeta) throw new Error('Не удалось определить индекс вопроса')
      if (!payloadValid) throw new Error('Payload JSON некорректен')

      return apiFetch<{ ok: boolean; error?: string }>(`/questions/${selectedQuestionId}`, {
        method: 'PUT',
        body: JSON.stringify({
          title: editTitle,
          test_id: activeTest,
          question_index: selectedMeta.index,
          payload: editPayload,
          is_active: editActive,
        }),
      })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['questions'] })
      await queryClient.invalidateQueries({ queryKey: ['questions-meta'] })
      await queryClient.invalidateQueries({ queryKey: ['question-detail', selectedQuestionId] })
      await queryClient.invalidateQueries({ queryKey: ['test-builder-graph-preview', activeTest] })
      setMessage('Вопрос сохранён. Изменения сразу доступны в боте.')
      window.setTimeout(() => setMessage(''), 2500)
    },
    onError: (err) => {
      setMessage(err instanceof Error ? err.message : 'Не удалось сохранить вопрос')
    },
  })

  const [edgeMatch, setEdgeMatch] = useState<BranchMatchMode>('always')
  const [edgeWhen, setEdgeWhen] = useState('')
  const [edgeFallback, setEdgeFallback] = useState(false)
  const [edgeAction, setEdgeAction] = useState<BranchAction>('next')
  const [edgeReason, setEdgeReason] = useState('')
  const [edgeTemplateKey, setEdgeTemplateKey] = useState('')
  const [edgePriority, setEdgePriority] = useState(0)
  const [edgeCustomLabel, setEdgeCustomLabel] = useState('')

  useEffect(() => {
    if (!selectedEdge) return
    const data = normalizeEdgeData(selectedEdge.data)
    setEdgeMatch(data.match)
    setEdgeWhen(data.when || '')
    setEdgeFallback(Boolean(data.fallback))
    setEdgeAction(data.action)
    setEdgeReason(data.reason || '')
    setEdgeTemplateKey(data.template_key || '')
    setEdgePriority(data.priority || 0)
    setEdgeCustomLabel(data.label || '')
  }, [selectedEdge])

  const saveEdgeSettings = () => {
    if (!selectedEdgeId) return
    const data = normalizeEdgeData({
      when: edgeMatch === 'always' ? '' : edgeWhen,
      match: edgeMatch,
      fallback: edgeFallback,
      action: edgeAction,
      reason: edgeReason,
      template_key: edgeTemplateKey,
      priority: edgePriority,
      label: edgeCustomLabel,
    })
    setEdges((current) =>
      current.map((edge) => {
        if (edge.id !== selectedEdgeId) return edge
        return {
          ...edge,
          data,
          label: edgeLabel(data),
        }
      }),
    )
    setMessage('Условие ветки сохранено.')
    window.setTimeout(() => setMessage(''), 1800)
  }

  const removeSelectedEdge = () => {
    if (!selectedEdgeId) return
    setEdges((current) => current.filter((edge) => edge.id !== selectedEdgeId))
    setSelectedEdgeId(null)
    setMessage('Ветка удалена.')
    window.setTimeout(() => setMessage(''), 1800)
  }

  const applyStatusTemplate = () => {
    const startNode = nodes.find((node) => node.type === 'start')
    const endNode = nodes.find((node) => node.type === 'end')
    if (!startNode || !endNode) {
      setMessage('Не найден start/end узел графа.')
      return
    }

    const statusNode = nodes.find((node) => {
      if (node.type !== 'question') return false
      const data = (node.data || {}) as Record<string, unknown>
      const key = String(data.key || '').toLowerCase()
      const prompt = String(data.prompt || '').toLowerCase()
      return key === 'status' || (prompt.includes('уч') && prompt.includes('работ'))
    })

    if (!statusNode) {
      setMessage('В графе не найден вопрос статуса (key=status).')
      return
    }

    const statusPosition = statusNode.position || { x: 0, y: 0 }

    const ensureNode = (current: FlowNode[], node: FlowNode): FlowNode[] => {
      const exists = current.find((item) => item.id === node.id)
      if (!exists) return [...current, node]
      return current.map((item) => (item.id === node.id ? { ...item, ...node, data: { ...item.data, ...node.data } } : item))
    }

    setNodes((current) => {
      let next = [...current]
      next = ensureNode(next, {
        id: 'vq_study_mode',
        type: 'question',
        position: { x: statusPosition.x - 360, y: statusPosition.y + 180 },
        data: {
          key: 'study_mode',
          title: 'Формат учёбы',
          prompt: 'Учитесь очно или заочно?',
          options: ['Очно', 'Заочно'],
          is_active: true,
        },
      } as FlowNode)
      next = ensureNode(next, {
        id: 'vq_study_schedule',
        type: 'question',
        position: { x: statusPosition.x - 360, y: statusPosition.y + 340 },
        data: {
          key: 'study_schedule',
          title: 'Совмещение 5/2',
          prompt: 'Сможете совмещать график 5/2 с 9:00 до 18:00?',
          options: ['Да, смогу', 'Нет, не смогу'],
          is_active: true,
        },
      } as FlowNode)
      next = ensureNode(next, {
        id: 'vq_notice',
        type: 'question',
        position: { x: statusPosition.x + 280, y: statusPosition.y + 320 },
        data: {
          key: 'notice_period',
          title: 'Готовность к старту',
          prompt: 'Сколько времени потребуется, чтобы завершить текущие дела и приступить к обучению?',
          placeholder: 'Например: 1-2 дня',
          is_active: true,
        },
      } as FlowNode)
      return next
    })

    setEdges((current) => {
      const currentStatusEdges = current.filter((edge) => edge.source === statusNode.id)
      const downstreamTarget = currentStatusEdges.find((edge) => edge.target !== endNode.id)?.target || endNode.id

      const controlledSources = new Set([
        startNode.id,
        statusNode.id,
        'vq_study_mode',
        'vq_study_schedule',
        'vq_notice',
      ])

      const kept = current.filter((edge) => !controlledSources.has(edge.source))
      const templateEdges: FlowEdge[] = [
        makeBranchEdge(startNode.id, statusNode.id, { match: 'always', fallback: true, action: 'next', label: 'start' }),

        makeBranchEdge(statusNode.id, 'vq_study_mode', { match: 'equals', when: 'Учусь', action: 'next' }),
        makeBranchEdge(statusNode.id, 'vq_notice', { match: 'equals', when: 'Работаю', action: 'next' }),
        makeBranchEdge(statusNode.id, 'vq_notice', { match: 'equals', when: 'Ищу работу', action: 'next' }),
        makeBranchEdge(statusNode.id, 'vq_notice', { match: 'equals', when: 'Предприниматель', action: 'next' }),
        makeBranchEdge(statusNode.id, 'vq_notice', { match: 'always', fallback: true, action: 'next' }),

        makeBranchEdge('vq_study_mode', 'vq_study_schedule', { match: 'equals', when: 'Очно', action: 'next' }),
        makeBranchEdge('vq_study_mode', 'vq_notice', { match: 'equals', when: 'Заочно', action: 'next' }),
        makeBranchEdge('vq_study_mode', 'vq_notice', { match: 'always', fallback: true, action: 'next' }),

        makeBranchEdge('vq_study_schedule', 'vq_notice', { match: 'equals', when: 'Да, смогу', action: 'next' }),
        makeBranchEdge('vq_study_schedule', 'vq_notice', { match: 'always', fallback: true, action: 'next' }),

        makeBranchEdge('vq_notice', downstreamTarget, { match: 'always', fallback: true, action: 'next' }),
      ]
      return [...kept, ...templateEdges]
    })

    setSelectedQuestionId(null)
    setSelectedEdgeId(null)
    setMessage('Применён шаблон ветки: статус -> учёба/работа -> готовность к старту.')
    window.setTimeout(() => setMessage(''), 3000)
  }

  const [previewAnswers, setPreviewAnswers] = useState<string[]>([])
  const [previewInput, setPreviewInput] = useState('')

  useEffect(() => {
    setPreviewAnswers([])
    setPreviewInput('')
  }, [activeTest])

  const previewQuery = useQuery<GraphPreviewPayload>({
    queryKey: ['test-builder-graph-preview', activeTest, graphForPreviewHash, previewAnswers],
    enabled: Boolean(activeTest && nodes.length > 0),
    retry: false,
    queryFn: () =>
      apiFetch<GraphPreviewPayload>('/test-builder/graph/preview', {
        method: 'POST',
        body: JSON.stringify({
          test_id: activeTest,
          graph: graphForSave,
          answers: previewAnswers,
        }),
      }),
  })

  const nextPreviewQuestion = previewQuery.data?.next_question || null

  const pushPreviewAnswer = (rawAnswer: string) => {
    const answer = rawAnswer.trim()
    if (!answer) return
    setPreviewAnswers((prev) => [...prev, answer])
    setPreviewInput('')
  }

  const undoPreviewAnswer = () => {
    setPreviewAnswers((prev) => prev.slice(0, -1))
    setPreviewInput('')
  }

  const resetPreview = () => {
    setPreviewAnswers([])
    setPreviewInput('')
  }

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <header className="glass glass--elevated page-header page-header--row">
          <div className="test-builder-graph__header-copy">
            <h1 className="title test-builder-graph__header-title">Конструктор тестов: Граф</h1>
            <div className="subtitle test-builder-graph__header-subtitle">
              v2: if/else ветки, reject-сценарии, редактирование вопросов и live-превью бота.
            </div>
          </div>
          <div className="toolbar toolbar--compact">
            <Link to="/app/test-builder" className="ui-btn ui-btn--ghost">Список</Link>
            <Link to="/app/system" className="ui-btn ui-btn--ghost">Bot Center</Link>
          </div>
        </header>

        <section className="glass page-section">
          <div className="toolbar test-builder-graph__toolbar">
            <div className="toolbar toolbar--compact test-builder-graph__toolbar-left">
              {groups.map((group) => (
                <button
                  key={group.test_id}
                  type="button"
                  className={`slot-create-tab ${activeTest === group.test_id ? 'is-active' : ''}`}
                  onClick={() => setActiveTest(group.test_id)}
                >
                  {group.title}
                </button>
              ))}
            </div>
            <div className="toolbar toolbar--compact test-builder-graph__toolbar-right">
              <button
                type="button"
                className="ui-btn ui-btn--ghost ui-btn--sm"
                onClick={applyStatusTemplate}
                disabled={!activeTest || nodes.length === 0}
              >
                Шаблон: статус-развилка
              </button>
              <button
                type="button"
                className="ui-btn ui-btn--primary ui-btn--sm"
                onClick={() => applyMutation.mutate()}
                disabled={applyMutation.isPending || !activeTest}
              >
                {applyMutation.isPending ? 'Применяем...' : 'Применить в боте'}
              </button>
            </div>
          </div>

          {message && <p className="subtitle test-builder-graph__message">{message}</p>}
          {graphQuery.isLoading && <p className="subtitle">Загрузка графа...</p>}
          {graphQuery.isError && <p className="text-danger">Ошибка: {(graphQuery.error as Error).message}</p>}

          <div className="test-builder-grid test-builder-graph__layout">
            <div className="test-builder-graph__main">
              <div className="rs-flow-canvas test-builder-graph__canvas-wrap">
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnect}
                  onNodeClick={onNodeClick}
                  onEdgeClick={onEdgeClick}
                  onPaneClick={() => {
                    setSelectedQuestionId(null)
                    setSelectedEdgeId(null)
                  }}
                  nodeTypes={nodeTypes}
                  fitView
                  fitViewOptions={{ padding: 0.2 }}
                  proOptions={{ hideAttribution: true }}
                >
                  <Background />
                  <Controls />
                  <MiniMap pannable zoomable />
                </ReactFlow>
              </div>

              <div className="glass test-builder-graph__preview">
                <div className="data-card__header test-builder-graph__preview-header">
                  <div>
                    <h3 className="section-title test-builder-graph__preview-title">Тестовая среда (превью бота)</h3>
                    <p className="subtitle test-builder-graph__preview-subtitle">
                      Прогоняет текущий граф и показывает реакцию бота на ответы кандидата.
                    </p>
                  </div>
                  <div className="toolbar toolbar--compact">
                    <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={undoPreviewAnswer} disabled={previewAnswers.length === 0}>
                      Шаг назад
                    </button>
                    <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={resetPreview} disabled={previewAnswers.length === 0}>
                      Сброс
                    </button>
                  </div>
                </div>

                {previewQuery.isLoading && <p className="subtitle">Рассчитываем превью...</p>}
                {previewQuery.isError && (
                  <p className="text-danger test-builder-graph__preview-error">
                    Ошибка превью: {(previewQuery.error as Error).message}
                  </p>
                )}

                {previewQuery.data && (
                  <div className="test-builder-graph__preview-body">
                    <div className="subtitle test-builder-graph__header-subtitle">
                      Вопросов в графе: {previewQuery.data.base_count}. Веток в сценарии: {previewQuery.data.sequence_count}.
                    </div>

                    <div style={{ display: 'grid', gap: 8 }}>
                      {previewQuery.data.steps.length === 0 && (
                        <p className="subtitle" style={{ margin: 0 }}>
                          Запуск с первого вопроса. Введите ответ ниже.
                        </p>
                      )}

                      {previewQuery.data.steps.map((step, idx) => (
                        <article key={`${step.question.key}-${idx}`} className="glass glass--subtle" style={{ padding: 12 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
                            <strong>{idx + 1}. {step.question.key}</strong>
                            <span className={`status-badge status-badge--${step.status === 'ok' ? 'success' : 'warning'}`}>
                              {step.status}
                            </span>
                          </div>
                          <div className="subtitle" style={{ marginTop: 6 }}>{formatPrompt(step.question.prompt)}</div>
                          <div style={{ marginTop: 8 }}>
                            <strong>Ответ:</strong> {step.answer || '—'}
                          </div>
                          {step.reaction?.message ? (
                            <div className="subtitle" style={{ marginTop: 6 }}>{step.reaction.message}</div>
                          ) : null}
                          {step.reaction?.edge_label ? (
                            <div className="subtitle" style={{ marginTop: 4 }}>
                              Ветка: <code>{step.reaction.edge_label}</code>
                            </div>
                          ) : null}
                          {step.reaction?.template_key ? (
                            <div className="subtitle" style={{ marginTop: 4 }}>
                              Шаблон: <code>{step.reaction.template_key}</code>
                            </div>
                          ) : null}
                        </article>
                      ))}
                    </div>

                    {!previewQuery.data.done && nextPreviewQuestion && (
                      <div className="glass glass--subtle" style={{ padding: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
                          <strong>Следующий вопрос: {nextPreviewQuestion.key}</strong>
                          <span className={`status-badge status-badge--${nextPreviewQuestion.kind === 'choice' ? 'info' : 'muted'}`}>
                            {nextPreviewQuestion.kind}
                          </span>
                        </div>
                        <div className="subtitle" style={{ marginTop: 6 }}>{nextPreviewQuestion.prompt || '—'}</div>

                        {nextPreviewQuestion.kind === 'choice' && nextPreviewQuestion.options.length > 0 && (
                          <div className="toolbar" style={{ marginTop: 10, flexWrap: 'wrap', gap: 8 }}>
                            {nextPreviewQuestion.options.map((opt) => (
                              <button
                                key={`${nextPreviewQuestion.key}-${opt}`}
                                type="button"
                                className="ui-btn ui-btn--ghost ui-btn--sm"
                                onClick={() => pushPreviewAnswer(opt)}
                              >
                                {opt}
                              </button>
                            ))}
                          </div>
                        )}

                        {(nextPreviewQuestion.kind === 'text' || nextPreviewQuestion.options.length === 0) && (
                          <div style={{ marginTop: 10, display: 'grid', gap: 8 }}>
                            <input
                              className="ui-input"
                              value={previewInput}
                              onChange={(e) => setPreviewInput(e.target.value)}
                              placeholder={nextPreviewQuestion.placeholder || 'Введите ответ'}
                            />
                            <div>
                              <button
                                type="button"
                                className="ui-btn ui-btn--primary ui-btn--sm"
                                onClick={() => pushPreviewAnswer(previewInput)}
                              >
                                Ответить
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {previewQuery.data.done && (
                      <p className="subtitle" style={{ margin: 0 }}>
                        Сценарий завершён: бот перейдёт к следующему этапу после последнего вопроса.
                      </p>
                    )}

                    {previewQuery.data.halted && previewQuery.data.halt_reason === 'reject' && (
                      <p className="text-danger" style={{ margin: 0 }}>
                        Сценарий завершён блокирующей веткой (reject).
                      </p>
                    )}
                  </div>
                )}
              </div>

              {graphQuery.data?.updated_at && (
                <p className="subtitle" style={{ marginBottom: 0 }}>
                  Последнее сохранение графа: {graphQuery.data.updated_at}
                </p>
              )}
            </div>

            <aside className="glass test-builder-graph__preview">
              {!selectedQuestionId && !selectedEdgeId && (
                <>
                  <h3 className="section-title" style={{ marginTop: 0 }}>Редактор графа</h3>
                  <p className="subtitle">
                    Нажмите на узел вопроса для редактирования текста/payload или на ребро для настройки if/else условий.
                  </p>
                  <div className="subtitle" style={{ marginTop: 8 }}>
                    Поддержка:
                    {' '}
                    <code>if = значение</code>,
                    {' '}
                    <code>contains</code>,
                    {' '}
                    <code>else (fallback)</code>,
                    {' '}
                    <code>reject</code>
                  </div>
                </>
              )}

              {selectedEdge && (
                <>
                  <div className="data-card__header" style={{ marginBottom: 12 }}>
                    <div>
                      <h3 className="section-title" style={{ marginTop: 0, marginBottom: 4 }}>Редактор ветки (if/else)</h3>
                      <div className="subtitle" style={{ margin: 0 }}>
                        {nodeLabelById.get(selectedEdge.source) || selectedEdge.source}
                        {' -> '}
                        {nodeLabelById.get(selectedEdge.target) || selectedEdge.target}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gap: 10 }}>
                    <label className="form-group">
                      <span className="form-group__label">Тип условия</span>
                      <select value={edgeMatch} onChange={(e) => setEdgeMatch(e.target.value as BranchMatchMode)}>
                        <option value="always">else (без условия)</option>
                        <option value="equals">if = точное совпадение</option>
                        <option value="contains">if contains</option>
                      </select>
                    </label>

                    {edgeMatch !== 'always' && (
                      <label className="form-group">
                        <span className="form-group__label">Значение условия</span>
                        <input
                          className="ui-input"
                          value={edgeWhen}
                          onChange={(e) => setEdgeWhen(e.target.value)}
                          placeholder="Например: Учусь"
                        />
                      </label>
                    )}

                    <label className="form-group">
                      <span className="form-group__label">Действие</span>
                      <select value={edgeAction} onChange={(e) => setEdgeAction(e.target.value as BranchAction)}>
                        <option value="next">Перейти к следующему узлу</option>
                        <option value="reject">Блокировать (reject)</option>
                      </select>
                    </label>

                    <label className="form-group">
                      <span className="form-group__label">
                        <input
                          type="checkbox"
                          checked={edgeFallback}
                          onChange={(e) => setEdgeFallback(e.target.checked)}
                        />{' '}
                        Fallback ветка (использовать как else)
                      </span>
                    </label>

                    <label className="form-group">
                      <span className="form-group__label">Приоритет</span>
                      <input
                        className="ui-input"
                        type="number"
                        value={edgePriority}
                        onChange={(e) => setEdgePriority(Number(e.target.value) || 0)}
                      />
                    </label>

                    <label className="form-group">
                      <span className="form-group__label">Кастомный label</span>
                      <input
                        className="ui-input"
                        value={edgeCustomLabel}
                        onChange={(e) => setEdgeCustomLabel(e.target.value)}
                        placeholder="Опционально"
                      />
                    </label>

                    <label className="form-group">
                      <span className="form-group__label">Причина reject (опционально)</span>
                      <input
                        className="ui-input"
                        value={edgeReason}
                        onChange={(e) => setEdgeReason(e.target.value)}
                        placeholder="Почему блокируем"
                      />
                    </label>

                    <label className="form-group">
                      <span className="form-group__label">Template key (опционально)</span>
                      <input
                        className="ui-input"
                        value={edgeTemplateKey}
                        onChange={(e) => setEdgeTemplateKey(e.target.value)}
                        placeholder="Например: t1_schedule_reject"
                      />
                    </label>

                    <div className="toolbar toolbar--compact" style={{ marginTop: 6 }}>
                      <button type="button" className="ui-btn ui-btn--primary" onClick={saveEdgeSettings}>
                        Сохранить ветку
                      </button>
                      <button type="button" className="ui-btn ui-btn--danger" onClick={removeSelectedEdge}>
                        Удалить ветку
                      </button>
                    </div>
                  </div>
                </>
              )}

              {selectedQuestionId && (
                <>
                  <div className="data-card__header" style={{ marginBottom: 12 }}>
                    <div>
                      <h3 className="section-title" style={{ marginTop: 0, marginBottom: 4 }}>Блок в графе</h3>
                      <div className="subtitle" style={{ margin: 0 }}>
                        ID: <code>{selectedQuestionId}</code>
                        {selectedMeta ? ` · Позиция: ${selectedMeta.index}` : ''}
                      </div>
                    </div>
                    <div className="toolbar toolbar--compact">
                      <Link
                        to="/app/questions/$questionId/edit"
                        params={{ questionId: String(selectedQuestionId) }}
                        className="ui-btn ui-btn--ghost ui-btn--sm"
                      >
                        Полный экран
                      </Link>
                    </div>
                  </div>

                  {detailQuery.isLoading && <p className="subtitle">Загрузка вопроса...</p>}
                  {detailQuery.isError && <p className="text-danger">Ошибка: {(detailQuery.error as Error).message}</p>}

                  {detailQuery.data && (
                    <div style={{ display: 'grid', gap: 12 }}>
                      <label className="form-group">
                        <span className="form-group__label">Заголовок</span>
                        <input
                          className="ui-input"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                        />
                      </label>

                      <label className="form-group">
                        <span className="form-group__label">
                          <input
                            type="checkbox"
                            checked={editActive}
                            onChange={(e) => setEditActive(e.target.checked)}
                          />{' '}
                          Активен
                        </span>
                      </label>

                      <div>
                        <div className="form-group__label" style={{ marginBottom: 6 }}>Payload (JSON)</div>
                        <QuestionPayloadEditor
                          value={editPayload}
                          onChange={setEditPayload}
                          onValidityChange={(ok) => setPayloadValid(ok)}
                        />
                      </div>

                      <button
                        type="button"
                        className="ui-btn ui-btn--primary"
                        onClick={() => saveMutation.mutate()}
                        disabled={saveMutation.isPending || !payloadValid}
                      >
                        {saveMutation.isPending ? 'Сохраняем...' : 'Сохранить вопрос'}
                      </button>
                    </div>
                  )}
                </>
              )}
            </aside>
          </div>
        </section>
      </div>
    </RoleGuard>
  )
}
