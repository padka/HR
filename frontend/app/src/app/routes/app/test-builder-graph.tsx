import { useEffect, useMemo, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { useMutation, useQuery } from '@tanstack/react-query'
import { RoleGuard } from '@/app/components/RoleGuard'
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

type QuestionGroup = { test_id: string; title: string }

type GraphPayload = {
  ok: boolean
  test_id: string
  graph: { schema: string; nodes: any[]; edges: any[] }
  updated_at: string | null
}

function StartNode(props: NodeProps) {
  const label = typeof (props.data as any)?.label === 'string' ? (props.data as any).label : 'Start'
  return (
    <div className="rs-flow-node rs-flow-node--start">
      <div className="rs-flow-node__title">{label}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

function EndNode(props: NodeProps) {
  const label = typeof (props.data as any)?.label === 'string' ? (props.data as any).label : 'End'
  return (
    <div className="rs-flow-node rs-flow-node--end">
      <Handle type="target" position={Position.Top} />
      <div className="rs-flow-node__title">{label}</div>
    </div>
  )
}

function QuestionNode(props: NodeProps) {
  const data = props.data as any
  const qid = typeof data?.question_id === 'number' ? data.question_id : null
  const title = typeof data?.title === 'string' ? data.title : 'Вопрос'
  return (
    <div className="rs-flow-node rs-flow-node--question">
      <Handle type="target" position={Position.Top} />
      <div className="rs-flow-node__title">{title}</div>
      <div className="rs-flow-node__meta">
        ID: <code>{qid ?? '—'}</code>
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

const nodeTypes = {
  start: StartNode,
  end: EndNode,
  question: QuestionNode,
}

function stripNode(node: Node): any {
  return {
    id: node.id,
    type: node.type,
    position: node.position,
    data: node.data,
  }
}

function stripEdge(edge: Edge): any {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.sourceHandle,
    targetHandle: edge.targetHandle,
  }
}

export function TestBuilderGraphPage() {
  const questionsMeta = useQuery({
    queryKey: ['questions-meta'],
    queryFn: () => apiFetch<any[]>('/questions'),
  })

  const groups: QuestionGroup[] = useMemo(() => {
    const raw = questionsMeta.data || []
    return raw.map((g: any) => ({ test_id: String(g.test_id), title: String(g.title || g.test_id) }))
  }, [questionsMeta.data])

  const [activeTest, setActiveTest] = useState<string>('')
  useEffect(() => {
    if (!activeTest && groups.length) setActiveTest(groups[0].test_id)
  }, [activeTest, groups])

  const graphQuery = useQuery({
    queryKey: ['test-builder-graph', activeTest],
    enabled: Boolean(activeTest),
    queryFn: async () => {
      const qs = new URLSearchParams({ test_id: activeTest })
      return apiFetch<GraphPayload>(`/test-builder/graph?${qs.toString()}`)
    },
  })

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [message, setMessage] = useState('')

  useEffect(() => {
    const payload = graphQuery.data
    if (!payload?.graph) return
    const rawNodes = Array.isArray(payload.graph.nodes) ? payload.graph.nodes : []
    const rawEdges = Array.isArray(payload.graph.edges) ? payload.graph.edges : []
    setNodes(rawNodes as any)
    setEdges(rawEdges as any)
    setMessage('')
  }, [graphQuery.data, setEdges, setNodes])

  const graphForSave = useMemo(() => {
    return {
      schema: 'xyflow_v1',
      nodes: nodes.map(stripNode),
      edges: edges.map(stripEdge),
    }
  }, [nodes, edges])

  const applyMutation = useMutation({
    mutationFn: async () => {
      if (!activeTest) throw new Error('Test not selected')
      return apiFetch<{ ok: boolean; error?: string }>('/test-builder/graph/apply', {
        method: 'POST',
        body: JSON.stringify({ test_id: activeTest, graph: graphForSave }),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['questions'] })
      queryClient.invalidateQueries({ queryKey: ['test-builder-graph', activeTest] })
      setMessage('Граф применён. Бот обновит вопросы автоматически.')
      window.setTimeout(() => setMessage(''), 2500)
    },
    onError: (err) => {
      setMessage(err instanceof Error ? err.message : 'Не удалось применить граф')
    },
  })

  const onConnect = (connection: Connection) => {
    setEdges((eds) => addEdge(connection, eds))
  }

  return (
    <RoleGuard allow={['admin']}>
      <div className="page">
        <header className="glass glass--elevated page-header page-header--row">
          <div style={{ display: 'grid', gap: 4 }}>
            <h1 className="title" style={{ margin: 0 }}>Конструктор тестов: Граф</h1>
            <div className="subtitle" style={{ margin: 0 }}>
              v2 (beta): схема блоков как в n8n. Сейчас поддерживается только линейный граф (без ветвлений).
            </div>
          </div>
          <div className="toolbar toolbar--compact">
            <Link to="/app/test-builder" className="ui-btn ui-btn--ghost">Список</Link>
            <Link to="/app/system" className="ui-btn ui-btn--ghost">Bot Center</Link>
          </div>
        </header>

        <section className="glass page-section">
          <div className="toolbar" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
            <div className="toolbar toolbar--compact">
              {groups.map((g) => (
                <button
                  key={g.test_id}
                  type="button"
                  className={`slot-create-tab ${activeTest === g.test_id ? 'is-active' : ''}`}
                  onClick={() => setActiveTest(g.test_id)}
                >
                  {g.title}
                </button>
              ))}
            </div>
            <div className="toolbar toolbar--compact">
              <button
                type="button"
                className="ui-btn ui-btn--primary ui-btn--sm"
                onClick={() => applyMutation.mutate()}
                disabled={applyMutation.isPending || !activeTest}
              >
                {applyMutation.isPending ? 'Применяем…' : 'Применить в боте'}
              </button>
            </div>
          </div>

          {message && <p className="subtitle" style={{ marginTop: 0 }}>{message}</p>}
          {graphQuery.isLoading && <p className="subtitle">Загрузка графа…</p>}
          {graphQuery.isError && <p className="text-danger">Ошибка: {(graphQuery.error as Error).message}</p>}

          <div style={{ height: 640 }} className="rs-flow-canvas">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              nodeTypes={nodeTypes as any}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              proOptions={{ hideAttribution: true }}
            >
              <Background />
              <Controls />
              <MiniMap pannable zoomable />
            </ReactFlow>
          </div>

          {graphQuery.data?.updated_at && (
            <p className="subtitle" style={{ marginBottom: 0 }}>
              Последнее сохранение графа: {graphQuery.data.updated_at}
            </p>
          )}
        </section>
      </div>
    </RoleGuard>
  )
}
