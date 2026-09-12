import { useCallback, useEffect, useRef, useState } from 'react'
import { sendChatMessage } from '../api'
import type { Server } from '../types'
import { ChatMessageBody } from './ChatMessageBody'

export type ChatMessage = {
  role: 'user' | 'assistant'
  text: string
  servers?: string[]
}

type Props = {
  activeServers: Server[]
}

export function ChatPanel({ activeServers }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [serverId, setServerId] = useState<string>('all')
  const [sending, setSending] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const send = useCallback(async () => {
    const text = input.trim()
    if (!text || sending) return

    setChatError(null)
    setMessages((prev) => [...prev, { role: 'user', text }])
    setInput('')
    setSending(true)

    const sid = serverId === 'all' ? null : Number(serverId)
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 130_000)

    try {
      const res = await sendChatMessage(text, sid, controller.signal)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', text: res.reply, servers: res.servers_in_context },
      ])
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.name === 'AbortError'
            ? 'Request timed out. The model may still be loading — try again in a moment.'
            : err.message
          : 'Chat failed'
      setChatError(msg)
      setInput(text)
      setMessages((prev) => prev.slice(0, -1))
    } finally {
      window.clearTimeout(timeout)
      setSending(false)
      inputRef.current?.focus()
    }
  }, [input, sending, serverId])

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void send()
    }
  }

  return (
    <section className="chat-panel">
      <div className="chat-toolbar">
        <label className="chat-scope-label">
          Scope
          <select
            className="chat-scope"
            value={serverId}
            onChange={(e) => setServerId(e.target.value)}
            disabled={sending}
          >
            <option value="all">All connected ({activeServers.length})</option>
            {activeServers.map((s) => (
              <option key={s.id} value={String(s.id)}>
                {s.server_name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="chat-messages" aria-live="polite">
        {messages.length === 0 && !sending && (
          <p className="chat-empty">Ask about health, GPUs, disk, or alerts for your connected servers.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble ${m.role}`}>
            {m.role === 'assistant' ? (
              <ChatMessageBody text={m.text} />
            ) : (
              <p className="chat-user-text">{m.text}</p>
            )}
            {m.servers?.length ? (
              <span className="chat-context-tag">{m.servers.join(', ')}</span>
            ) : null}
          </div>
        ))}
        {sending && (
          <div className="chat-bubble assistant chat-pending">
            <span className="chat-spinner" aria-hidden />
            Getting answer… this can take up to 2 minutes.
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {chatError && <p className="chat-error">{chatError}</p>}

      <div className="chat-compose">
        <textarea
          ref={inputRef}
          rows={2}
          placeholder="Message… (Enter to send, Shift+Enter for new line)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={sending}
        />
        <button
          type="button"
          className="btn primary chat-send"
          disabled={sending}
          onClick={() => void send()}
        >
          {sending ? '…' : 'Send'}
        </button>
      </div>
    </section>
  )
}
