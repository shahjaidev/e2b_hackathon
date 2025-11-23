import type React from 'react'
import { useRef, useEffect, useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Send } from 'lucide-react'
import { useCode } from '@/contexts/code-context'
import { MarkdownContent } from '@/components/markdown-content'
import CodeMessagePreview from '@/components/code-message-preview'
import Image from 'next/image'

interface Message {
    id: string
    role: string
    content: string
    type?: string
    fragmentId?: string
    code?: string
    charts?: Array<{ filename: string; url: string }>
    executionOutput?: string[]
}

interface ChatProps {
    messages: Message[]
    onSendMessage: (message: string) => void
    isLoading: boolean
    status: string | null
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'

export function Chat({
    messages,
    onSendMessage,
    isLoading,
    status,
}: ChatProps) {
    const [input, setInput] = useState('')
    const messagesEndRef = useRef<HTMLDivElement | null>(null)
    const { toggleCode, fragments } = useCode()

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [])

    useEffect(() => {
        scrollToBottom()
    }, [messages, scrollToBottom])

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()
        if (input.trim() && !isLoading) {
            onSendMessage(input.trim())
            setInput('')
        }
    }

    const renderMessage = useCallback(
        (message: Message) => {
            const messageKey = `message-${message.id}-${message.type || 'default'}`

            if (message.role === 'user') {
                return (
                    <div key={messageKey} className="flex justify-end mb-4">
                        <div className="bg-primary text-primary-foreground rounded-lg p-4 max-w-[80%]">
                            {message.content}
                        </div>
                    </div>
                )
            }

            if (message.type === 'system') {
                return (
                    <div key={messageKey} className="flex justify-center mb-4">
                        <div className="bg-muted/50 rounded-lg p-3 max-w-[80%] text-sm text-muted-foreground">
                            {message.content}
                        </div>
                    </div>
                )
            }

            if (message.type === 'error') {
                return (
                    <div key={messageKey} className="flex mb-4">
                        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4 max-w-[80%]">
                            <div className="text-destructive font-medium mb-1">
                                Error
                            </div>
                            <div className="text-sm">{message.content}</div>
                        </div>
                    </div>
                )
            }

            if (message.type === 'code' && message.code) {
                // Find or create fragment for this code
                let fragment = fragments.find((f) => f.file_path === 'analysis.py')
                if (!fragment && message.code) {
                    fragment = {
                        id: `code_${message.id}`,
                        title: 'Analysis Code',
                        description: 'Generated analysis code',
                        file_path: 'analysis.py',
                        dependencies: [],
                        port: 0,
                    }
                }
                return (
                    <div key={messageKey} className="space-y-2 mb-4">
                        <CodeMessagePreview
                            message={message}
                            fragment={fragment}
                            toggleCode={toggleCode}
                        />
                        {message.charts && message.charts.length > 0 && (
                            <div className="flex flex-col gap-2">
                                {message.charts.map((chart, idx) => (
                                    <div
                                        key={idx}
                                        className="bg-muted rounded-lg p-2 max-w-[80%]"
                                    >
                                        <img
                                            src={`${API_BASE_URL}${chart.url}`}
                                            alt={`Chart ${idx + 1}`}
                                            className="max-w-full h-auto rounded"
                                        />
                                    </div>
                                ))}
                            </div>
                        )}
                        {message.executionOutput && message.executionOutput.length > 0 && (
                            <div className="bg-muted rounded-lg p-4 max-w-[80%] border border-border">
                                <div className="text-xs font-semibold text-foreground mb-2 flex items-center gap-2">
                                    <span className="h-2 w-2 rounded-full bg-green-500"></span>
                                    Execution Output:
                                </div>
                                <pre className="text-xs font-mono whitespace-pre-wrap break-words">
                                    {message.executionOutput.join('\n')}
                                </pre>
                            </div>
                        )}
                        {message.type === 'code' && (!message.executionOutput || message.executionOutput.length === 0) && (
                            <div className="bg-muted/50 rounded-lg p-3 max-w-[80%] border border-dashed border-muted-foreground/30">
                                <div className="text-xs text-muted-foreground">
                                    ⏳ Code execution in progress or no output produced...
                                </div>
                            </div>
                        )}
                    </div>
                )
            }

            // Regular text message with potential charts
            return (
                <div key={messageKey} className="space-y-2 mb-4">
                    <div className="flex mb-4">
                        <div className="bg-muted rounded-lg p-4 max-w-[80%]">
                            <MarkdownContent content={message.content} />
                        </div>
                    </div>
                    {message.charts && message.charts.length > 0 && (
                        <div className="flex flex-col gap-2">
                            {message.charts.map((chart, idx) => (
                                <div
                                    key={idx}
                                    className="bg-muted rounded-lg p-2 max-w-[80%]"
                                >
                                    <img
                                        src={`${API_BASE_URL}${chart.url}`}
                                        alt={`Chart ${idx + 1}`}
                                        className="max-w-full h-auto rounded"
                                    />
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )
        },
        [fragments, toggleCode]
    )

    return (
        <div className="flex h-full overflow-hidden w-full flex-grow flex-col justify-between">
            <div className="h-full overflow-y-auto flex-grow">
                <div className="space-y-4 p-4">
                    {messages.map((message) => renderMessage(message))}
                    {isLoading && (
                        <div className="flex mb-4">
                            <div className="bg-muted rounded-lg p-4 max-w-[80%]">
                                <div className="flex items-center gap-2">
                                    <div className="h-4 w-4 rounded-full bg-secondary animate-pulse" />
                                    <div className="text-sm text-muted-foreground">
                                        {status || 'Processing...'}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>
            </div>
            <div className="flex flex-shrink-0 space-x-2 p-4 border-t bg-background">
                <form onSubmit={handleSubmit} className="flex flex-1 space-x-2">
                    <Input
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Type your message..."
                        disabled={isLoading}
                        className="flex-1"
                    />
                    <Button type="submit" disabled={isLoading}>
                        <Send className="h-4 w-4" />
                        <span className="sr-only">Send</span>
                    </Button>
                </form>
            </div>
        </div>
    )
}
