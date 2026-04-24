import { useState, useEffect } from 'react'
import { api } from '../lib/api'

interface MemoryData {
  short_term: {
    items: Array<{
      key: string
      value: any
      created_at: string
    }>
    count: number
  }
  long_term: {
    items: Record<string, {
      key: string
      value: any
      created_at: string
    }>
    count: number
  }
}

export default function MemoryPage() {
  const [memory, setMemory] = useState<MemoryData | null>(null)
  const [loading, setLoading] = useState(true)
  const [newKey, setNewKey] = useState('')
  const [newValue, setNewValue] = useState('')
  const [memoryType, setMemoryType] = useState<'short' | 'long'>('short')

  useEffect(() => {
    loadMemory()
  }, [])

  const loadMemory = async () => {
    try {
      const response = await api.get<MemoryData>('/memory')
      setMemory(response.data)
    } catch (error) {
      console.error('加载记忆失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const addMemory = async () => {
    if (!newKey || !newValue) return

    try {
      const endpoint = memoryType === 'short' ? '/memory/short-term' : '/memory/long-term'
      await api.post(endpoint, null, {
        params: { key: newKey, value: newValue },
      })
      setNewKey('')
      setNewValue('')
      loadMemory()
    } catch (error) {
      console.error('新增记忆失败:', error)
    }
  }

  const clearMemory = async (type: 'short' | 'long') => {
    if (!confirm(`确认清空全部${type === 'short' ? '短期' : '长期'}记忆吗？`)) return

    try {
      await api.delete(`/memory/${type}-term`)
      loadMemory()
    } catch (error) {
      console.error('清空记忆失败:', error)
    }
  }

  if (loading) {
    return <div className="text-center py-8 text-gray-500">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-gray-900">记忆</h2>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">新增记忆</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <select
              value={memoryType}
              onChange={(e) => setMemoryType(e.target.value as 'short' | 'long')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="short">短期记忆</option>
              <option value="long">长期记忆</option>
            </select>
          </div>
          <div>
            <input
              type="text"
              placeholder="键"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <input
              type="text"
              placeholder="值"
              value={newValue}
              onChange={(e) => setNewValue(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>
          <div>
            <button
              onClick={addMemory}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              添加
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b flex justify-between items-center">
          <h3 className="text-lg font-medium text-gray-900">
            短期记忆（{memory?.short_term.count || 0}）
          </h3>
          <button
            onClick={() => clearMemory('short')}
            className="px-3 py-1 text-sm text-red-600 hover:text-red-700"
          >
            清空
          </button>
        </div>
        <div className="p-6">
          {memory?.short_term.items && memory.short_term.items.length > 0 ? (
            <div className="space-y-2">
              {memory.short_term.items.map((item, i) => (
                <div key={i} className="p-3 bg-gray-50 rounded-lg">
                  <div className="font-medium text-gray-900">{item.key}</div>
                  <div className="text-sm text-gray-600 mt-1">
                    {typeof item.value === 'object' ? JSON.stringify(item.value) : String(item.value)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-500 py-4">没有短期记忆</div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b flex justify-between items-center">
          <h3 className="text-lg font-medium text-gray-900">
            长期记忆（{memory?.long_term.count || 0}）
          </h3>
          <button
            onClick={() => clearMemory('long')}
            className="px-3 py-1 text-sm text-red-600 hover:text-red-700"
          >
            清空
          </button>
        </div>
        <div className="p-6">
          {memory?.long_term.items && Object.keys(memory.long_term.items).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(memory.long_term.items).map(([key, item]) => (
                <div key={key} className="p-3 bg-gray-50 rounded-lg">
                  <div className="font-medium text-gray-900">{item.key}</div>
                  <div className="text-sm text-gray-600 mt-1">
                    {typeof item.value === 'object' ? JSON.stringify(item.value) : String(item.value)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-gray-500 py-4">没有长期记忆</div>
          )}
        </div>
      </div>
    </div>
  )
}
