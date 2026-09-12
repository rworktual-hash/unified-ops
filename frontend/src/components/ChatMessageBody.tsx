/** Lightweight formatting for assistant replies (no extra deps). */
export function ChatMessageBody({ text }: { text: string }) {
  const lines = text.split('\n')

  return (
    <div className="chat-message-body">
      {lines.map((line, i) => (
        <p key={i} className="chat-line">
          <InlineFormat text={line} />
        </p>
      ))}
    </div>
  )
}

function InlineFormat({ text }: { text: string }) {
  if (!text) return null
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i}>{part.slice(2, -2)}</strong>
        }
        return <span key={i}>{part}</span>
      })}
    </>
  )
}
