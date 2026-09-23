import { useCallback, useEffect, useRef, useState } from 'react'
import { streamChatMessage } from '../api'
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

const SUGGESTIONS = [
  'Which hosts are low on disk?',
  'Which GPUs are busy?',
  'What alerts are open?',
  'Summarize host health',
]

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

  const send = useCallback(async (raw?: string) => {
    const text = (raw ?? input).trim()
    if (!text || sending) return

    setChatError(null)
    setMessages((prev) => [...prev, { role: 'user', text }])
    setInput('')
    setSending(true)

    const sid = serverId === 'all' ? null : Number(serverId)
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), 130_000)
    const received = { text: '' }
    const shown = { text: '' }
    let timer = 0

    setMessages((prev) => [...prev, { role: 'assistant', text: '' }])

    const paint = (value: string) => {
      setMessages((prev) => {
        const next = [...prev]
        const last = next.length - 1
        if (next[last]?.role === 'assistant') {
          next[last] = { role: 'assistant', text: value }
        }
        return next
      })
    }

    try {
      let settled = false
      let failed: Error | null = null
      const incoming = streamChatMessage(
        text,
        sid,
        (chunk) => {
          received.text += chunk
        },
        controller.signal,
      ).then(
        () => {
          settled = true
        },
        (err: unknown) => {
          settled = true
          failed = err instanceof Error ? err : new Error('Chat failed')
        },
      )

      await new Promise<void>((resolve) => {
        const step = () => {
          const target = received.text
          const current = shown.text
          if (current.length < target.length) {
            const rest = target.slice(current.length)
            let end = 0
            while (end < rest.length && /\s/.test(rest[end])) end += 1
            const word = rest.slice(end).search(/\s/)
            end += word === -1 ? rest.length - end : word
            if (end < 1) end = 1
            shown.text = current + rest.slice(0, end)
            paint(shown.text)
            timer = window.setTimeout(step, 28)
            return
          }
          if (settled) {
            resolve()
            return
          }
          timer = window.setTimeout(step, 40)
        }
        void incoming.then(() => {
          settled = true
        })
        step()
      })
      if (failed) throw failed
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.name === 'AbortError'
            ? 'Request timed out. The model may still be loading — try again in a moment.'
            : err.message
          : 'Chat failed'
      setChatError(msg)
      if (!shown.text) {
        setInput(text)
        setMessages((prev) => prev.slice(0, -2))
      }
    } finally {
      window.clearTimeout(timeout)
      window.clearTimeout(timer)
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
        <span className="muted chat-toolbar-note">Latest collect for the scope you pick</span>
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
          <div className="chat-empty">
            <p className="chat-empty-title">Ask about the fleet</p>
            <p>Health, disk, GPUs, and alerts for the hosts in scope.</p>
            <div className="chat-suggestions">
              {SUGGESTIONS.map((question) => (
                <button
                  key={question}
                  type="button"
                  className="chat-suggestion"
                  disabled={sending}
                  onClick={() => void send(question)}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble ${m.role}`}>
            {m.role === 'assistant' ? (
              m.text === '' && sending && i === messages.length - 1 ? (
                <span className="chat-dots" aria-hidden>
                  <span />
                  <span />
                  <span />
                </span>
              ) : (
                <>
                  <ChatMessageBody text={m.text} />
                  {sending && i === messages.length - 1 ? <span className="chat-caret" aria-hidden /> : null}
                </>
              )
            ) : (
              <p className="chat-user-text">{m.text}</p>
            )}
          </div>
        ))}
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
