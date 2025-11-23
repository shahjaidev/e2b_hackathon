'use client'

import { useCallback, useEffect, useState, useRef } from 'react'
import { Chat } from '@/components/chat'
import { Header } from '@/components/header'
import { AppSidebar } from '@/components/app-sidebar'
import { CodeSidebar } from '@/components/code-sidebar'
import { useCode } from '@/contexts/code-context'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { Upload, X, Download, Link as LinkIcon } from 'lucide-react'

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

interface Conversation {
    id: string
    messages: Message[]
    sessionId: string
    uploadedFiles?: Array<{
        filename: string
        columns_info?: {
            columns: string[]
            shape: number[]
        }
    }>
    downloadedDocuments?: Array<{
        filename: string
        url: string
    }>
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000'

// Constants for storage management
const MAX_CONVERSATIONS = 20 // Maximum number of conversations to keep
const MAX_MESSAGES_PER_CONVERSATION = 100 // Maximum messages per conversation

// Helper function to clean up conversations
const cleanupConversations = (conversations: Conversation[]): Conversation[] => {
    // Sort by most recent (assuming id is timestamp-based)
    const sorted = [...conversations].sort((a, b) => {
        const aId = parseInt(a.id) || 0
        const bId = parseInt(b.id) || 0
        return bId - aId
    })
    
    // Keep only the most recent conversations
    const kept = sorted.slice(0, MAX_CONVERSATIONS)
    
    // Limit messages per conversation
    return kept.map(conv => ({
        ...conv,
        messages: conv.messages.slice(-MAX_MESSAGES_PER_CONVERSATION)
    }))
}

// Helper function to safely save to localStorage with cleanup
const saveConversationsToStorage = (conversations: Conversation[]) => {
    try {
        // First, try to clean up old conversations
        const cleaned = cleanupConversations(conversations)
        
        // Try to save
        const serialized = JSON.stringify(cleaned)
        localStorage.setItem('conversations', serialized)
        
        // If we had to clean up, update the conversations state
        if (cleaned.length < conversations.length) {
            return cleaned
        }
        // Check if any conversation had messages trimmed
        const cleanedMap = new Map(cleaned.map(c => [c.id, c]))
        const hadTrimming = conversations.some(conv => {
            const cleanedConv = cleanedMap.get(conv.id)
            return cleanedConv && cleanedConv.messages.length < conv.messages.length
        })
        if (hadTrimming) {
            return cleaned
        }
        return conversations
    } catch (error: any) {
        if (error.name === 'QuotaExceededError' || error.code === 22) {
            console.warn('localStorage quota exceeded, cleaning up old conversations...')
            // More aggressive cleanup
            const cleaned = cleanupConversations(conversations)
            
            // Try with even fewer conversations
            const moreCleaned = cleaned.slice(0, Math.max(5, MAX_CONVERSATIONS - 5))
            const limitedMessages = moreCleaned.map(conv => ({
                ...conv,
                messages: conv.messages.slice(-50) // Even fewer messages
            }))
            
            try {
                localStorage.setItem('conversations', JSON.stringify(limitedMessages))
                return limitedMessages
            } catch (e) {
                console.error('Still unable to save after cleanup:', e)
                // Last resort: keep only current conversation
                const currentId = localStorage.getItem('activeConversation')
                if (currentId) {
                    const current = conversations.find(c => c.id === currentId)
                    if (current) {
                        const minimal = [{
                            ...current,
                            messages: current.messages.slice(-20)
                        }]
                        try {
                            localStorage.setItem('conversations', JSON.stringify(minimal))
                            return minimal
                        } catch {
                            // Give up, clear everything
                            localStorage.removeItem('conversations')
                            return []
                        }
                    }
                }
                localStorage.removeItem('conversations')
                return []
            }
        }
        console.error('Error saving conversations to localStorage:', error)
        return conversations
    }
}

const Page = () => {
    const [conversations, setConversations] = useState<Conversation[]>([])
    const [currentConversationId, setCurrentConversationId] = useState<
        string | null
    >(null)
    const [isLoading, setIsLoading] = useState(false)
    const [status, setStatus] = useState<string | null>(null)
    const [uploadingFile, setUploadingFile] = useState(false)
    const [downloadingDrive, setDownloadingDrive] = useState(false)
    const [driveUrl, setDriveUrl] = useState('')
    const fileInputRef = useRef<HTMLInputElement>(null)
    const { setFragments, updateCode, isCodeOpen, syncWithLocalStorage } =
        useCode()

    useEffect(() => {
        try {
            const savedConversations = localStorage.getItem('conversations')
            if (savedConversations) {
                const parsedConversations = JSON.parse(savedConversations)
                // Clean up on load as well
                const cleaned = cleanupConversations(parsedConversations)
                setConversations(cleaned)

                const lastActiveConversation =
                    localStorage.getItem('activeConversation')
                if (lastActiveConversation) {
                    setCurrentConversationId(lastActiveConversation)
                }
            }
        } catch (error) {
            console.error('Error loading conversations from localStorage:', error)
            // Clear corrupted data
            localStorage.removeItem('conversations')
            setConversations([])
        }
    }, [])

    useEffect(() => {
        const cleaned = saveConversationsToStorage(conversations)
        // Only update state if cleanup happened
        if (cleaned.length !== conversations.length) {
            setConversations(cleaned)
            return
        }
        // Check if any conversation had messages trimmed
        const cleanedMap = new Map(cleaned.map(c => [c.id, c]))
        const hadTrimming = conversations.some(conv => {
            const cleanedConv = cleanedMap.get(conv.id)
            return cleanedConv && cleanedConv.messages.length < conv.messages.length
        })
        if (hadTrimming) {
            setConversations(cleaned)
        }
    }, [conversations])

    const handleConversationSwitch = useCallback(
        (conversationId: string) => {
            setCurrentConversationId(conversationId)
            localStorage.setItem('activeConversation', conversationId)
            syncWithLocalStorage(conversationId)
        },
        [syncWithLocalStorage]
    )

    useEffect(() => {
        if (currentConversationId) {
            handleConversationSwitch(currentConversationId)
        }
    }, [currentConversationId, handleConversationSwitch])

    const handleFileUpload = async (file: File) => {
        if (!currentConversationId) {
            alert('Please start a conversation first')
            return
        }

        const validExtensions = ['.csv', '.xlsx']
        const fileExtension = file.name.toLowerCase().substring(file.name.lastIndexOf('.'))
        if (!validExtensions.includes(fileExtension)) {
            alert('Please upload a CSV or Excel (.xlsx) file')
            return
        }

        setUploadingFile(true)
        setStatus('Uploading file...')

        try {
            const formData = new FormData()
            formData.append('file', file)
            formData.append('session_id', currentConversationId)

            let response: Response
            try {
                response = await fetch(`${API_BASE_URL}/api/upload`, {
                    method: 'POST',
                    body: formData,
                })
            } catch (fetchError: any) {
                // Network error (backend not running, CORS, etc.)
                throw new Error(
                    `Failed to connect to backend at ${API_BASE_URL}. Please make sure the backend server is running. Error: ${fetchError.message}`
                )
            }

            if (!response.ok) {
                let errorMessage = 'Upload failed'
                try {
                    const error = await response.json()
                    errorMessage = error.error || errorMessage
                } catch {
                    errorMessage = `Server returned error: ${response.status} ${response.statusText}`
                }
                throw new Error(errorMessage)
            }

            const result = await response.json()
            
            // Update conversation with file info (append to list)
            setConversations((prev) =>
                prev.map((conv) =>
                    conv.id === currentConversationId
                        ? {
                              ...conv,
                              uploadedFiles: [
                                  ...(conv.uploadedFiles || []),
                                  {
                                      filename: result.filename,
                                      columns_info: result.columns_info,
                                  },
                              ],
                          }
                        : conv
                )
            )

            // Add a system message about the upload
            const uploadMessage: Message = {
                id: `${Date.now()}-upload-${Math.random().toString(36).substring(2, 9)}`,
                role: 'assistant',
                content: `File "${result.filename}" uploaded successfully. The file has ${result.columns_info?.columns.length || 0} columns: ${result.columns_info?.columns.join(', ') || 'N/A'}`,
                type: 'system',
            }

            setConversations((prev) =>
                prev.map((conv) =>
                    conv.id === currentConversationId
                        ? {
                              ...conv,
                              messages: [...conv.messages, uploadMessage],
                          }
                        : conv
                )
            )

            setStatus(null)
        } catch (error: any) {
            console.error('Upload error:', error)
            const errorMessage = error.message || 'Upload failed'
            setStatus(`Upload failed: ${errorMessage}`)
            
            // Add error message to conversation
            const errorMsg: Message = {
                id: `${Date.now()}-error-${Math.random().toString(36).substring(2, 9)}`,
                role: 'assistant',
                content: `Upload failed: ${errorMessage}`,
                type: 'error',
            }
            
            setConversations((prev) =>
                prev.map((conv) =>
                    conv.id === currentConversationId
                        ? {
                              ...conv,
                              messages: [...conv.messages, errorMsg],
                          }
                        : conv
                )
            )
            
            setTimeout(() => setStatus(null), 5000)
        } finally {
            setUploadingFile(false)
        }
    }

    const handleGoogleDriveDownload = async () => {
        if (!currentConversationId) {
            alert('Please start a conversation first')
            return
        }

        if (!driveUrl.trim()) {
            alert('Please enter a Google Drive link')
            return
        }

        // Basic validation for Google Drive URL
        if (!driveUrl.includes('drive.google.com') && !driveUrl.includes('docs.google.com')) {
            alert('Please enter a valid Google Drive link')
            return
        }

        setDownloadingDrive(true)
        setStatus('Downloading from Google Drive...')

        try {
            const response = await fetch(`${API_BASE_URL}/api/download-google-drive`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: driveUrl,
                    session_id: currentConversationId,
                }),
            })

            if (!response.ok) {
                const error = await response.json()
                throw new Error(error.error || 'Download failed')
            }

            const result = await response.json()

            // Update conversation with document info
            setConversations((prev) =>
                prev.map((conv) =>
                    conv.id === currentConversationId
                        ? {
                              ...conv,
                              downloadedDocuments: [
                                  ...(conv.downloadedDocuments || []),
                                  {
                                      filename: result.filename,
                                      url: driveUrl,
                                  },
                              ],
                          }
                        : conv
                )
            )

            // Add a system message about the download
            const downloadMessage: Message = {
                id: `${Date.now()}-download-${Math.random().toString(36).substring(2, 9)}`,
                role: 'assistant',
                content: `Document "${result.filename}" downloaded from Google Drive successfully. You can now ask questions about the document content.`,
                type: 'system',
            }

            setConversations((prev) =>
                prev.map((conv) =>
                    conv.id === currentConversationId
                        ? {
                              ...conv,
                              messages: [...conv.messages, downloadMessage],
                          }
                        : conv
                )
            )

            setDriveUrl('')
            setStatus(null)
        } catch (error: any) {
            console.error('Google Drive download error:', error)
            const errorMessage = error.message || 'Download failed'
            setStatus(`Download failed: ${errorMessage}`)

            // Add error message to conversation
            const errorMsg: Message = {
                id: `${Date.now()}-error-${Math.random().toString(36).substring(2, 9)}`,
                role: 'assistant',
                content: `Download failed: ${errorMessage}`,
                type: 'error',
            }

            setConversations((prev) =>
                prev.map((conv) =>
                    conv.id === currentConversationId
                        ? {
                              ...conv,
                              messages: [...conv.messages, errorMsg],
                          }
                        : conv
                )
            )

            setTimeout(() => setStatus(null), 5000)
        } finally {
            setDownloadingDrive(false)
        }
    }

    const sendMessage = async (message: string) => {
        if (!currentConversationId) return

        setIsLoading(true)
        setStatus('Processing...')

        const currentConversation = conversations.find(
            (conv) => conv.id === currentConversationId
        )
        if (!currentConversation) return

        const userMessage: Message = {
            id: `${Date.now()}-${Math.random()}`,
            role: 'user',
            content: message,
        }

        setConversations((prev) =>
            prev.map((conv) =>
                conv.id === currentConversationId
                    ? { ...conv, messages: [...conv.messages, userMessage] }
                    : conv
            )
        )

        try {
            const response = await fetch(`${API_BASE_URL}/api/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message,
                    session_id: currentConversationId,
                }),
            })

            if (!response.ok) {
                const error = await response.json()
                throw new Error(error.error || 'Request failed')
            }

            const data = await response.json()

            // Debug logging
            console.log('Response data:', {
                has_code: data.has_code,
                has_execution_output: !!data.execution_output,
                execution_output_length: data.execution_output?.length || 0,
                execution_output_preview: data.execution_output?.slice(0, 2) || []
            })

            // If there's code, add it to the code context first
            let codeId: string | undefined
            if (data.code) {
                // Create a fragment for the code
                codeId = `code_${Date.now()}`
                const fragment = {
                    id: codeId,
                    title: 'Analysis Code',
                    description: 'Generated analysis code',
                    file_path: 'analysis.py',
                    dependencies: [],
                    port: 0,
                }
                
                setFragments([fragment])
                updateCode(codeId, data.code)
            }

            // Normalize execution output - ensure it's always an array of strings
            let executionOutput: string[] = []
            if (data.execution_output) {
                if (Array.isArray(data.execution_output)) {
                    executionOutput = data.execution_output.map((item: any) => 
                        typeof item === 'string' ? item : String(item)
                    )
                } else if (typeof data.execution_output === 'string') {
                    executionOutput = [data.execution_output]
                }
            }

            // Create assistant message with all the data
            const assistantMessage: Message = {
                id: `${Date.now()}-${Math.random()}`,
                role: 'assistant',
                content: data.response || 'No response',
                type: data.has_code ? 'code' : 'text',
                fragmentId: codeId,
                code: data.code,
                charts: data.charts || [],
                executionOutput: executionOutput,
            }

            setConversations((prev) =>
                prev.map((conv) =>
                    conv.id === currentConversationId
                        ? {
                              ...conv,
                              messages: [...conv.messages, assistantMessage],
                          }
                        : conv
                )
            )
        } catch (error: any) {
            console.error('Chat error:', error)
            const errorMessage: Message = {
                id: `${Date.now()}-error-${Math.random().toString(36).substring(2, 9)}`,
                role: 'assistant',
                content: `Error: ${error.message}`,
                type: 'error',
            }
            setConversations((prev) =>
                prev.map((conv) =>
                    conv.id === currentConversationId
                        ? {
                              ...conv,
                              messages: [...conv.messages, errorMessage],
                          }
                        : conv
                )
            )
        } finally {
            setIsLoading(false)
            setStatus(null)
        }
    }

    const createNewConversation = () => {
        const newId = Date.now().toString()
        setConversations((prev) => [
            ...prev,
            { id: newId, messages: [], sessionId: newId },
        ])
        handleConversationSwitch(newId)
    }

    const handleManualCleanup = () => {
        if (confirm('This will remove old conversations and keep only the 10 most recent. Continue?')) {
            const cleaned = cleanupConversations(conversations)
            const limited = cleaned.slice(0, 10).map(conv => ({
                ...conv,
                messages: conv.messages.slice(-50) // Keep only last 50 messages per conversation
            }))
            
            try {
                localStorage.setItem('conversations', JSON.stringify(limited))
                setConversations(limited)
                alert(`Cleanup complete! Kept ${limited.length} conversations.`)
            } catch (error: any) {
                if (error.name === 'QuotaExceededError') {
                    // More aggressive cleanup
                    const minimal = limited.slice(0, 5).map(conv => ({
                        ...conv,
                        messages: conv.messages.slice(-20)
                    }))
                    localStorage.setItem('conversations', JSON.stringify(minimal))
                    setConversations(minimal)
                    alert(`Storage still full. Kept only ${minimal.length} conversations.`)
                } else {
                    alert(`Cleanup failed: ${error.message}`)
                }
            }
        }
    }

    const handleClearAll = () => {
        if (confirm('This will DELETE ALL conversations. This cannot be undone. Continue?')) {
            localStorage.removeItem('conversations')
            localStorage.removeItem('activeConversation')
            // Clear all code data
            Object.keys(localStorage).forEach(key => {
                if (key.startsWith('code_data_')) {
                    localStorage.removeItem(key)
                }
            })
            setConversations([])
            setCurrentConversationId(null)
            alert('All conversations cleared!')
        }
    }

    const currentConversation = conversations.find(
        (conv) => conv.id === currentConversationId
    )

    return (
        <div className="flex h-screen w-screen">
            <AppSidebar
                conversations={conversations}
                currentConversationId={currentConversationId}
                onSelectConversation={handleConversationSwitch}
                onNewConversation={createNewConversation}
                onCleanup={handleManualCleanup}
                onClearAll={handleClearAll}
            />
            <div className="flex flex-col w-full justify-between">
                <Header
                    isConnected={true}
                    conversations={conversations}
                    currentConversationId={currentConversationId}
                    onSelectConversation={handleConversationSwitch}
                    onNewConversation={createNewConversation}
                />
                <div className="flex-grow w-full h-full overflow-hidden">
                    <div className="w-full h-full grid grid-cols-2">
                        <main
                            className={cn(
                                'h-full w-full transition-all overflow-scroll flex flex-col duration-200 ease-in-out',
                                isCodeOpen ? 'col-span-1' : 'col-span-2'
                            )}
                        >
                            {currentConversation ? (
                                <>
                                    {/* File Upload Section */}
                                    <div className="border-b p-2 space-y-2">
                                        <div className="flex items-center gap-2">
                                        <input
                                            ref={fileInputRef}
                                            type="file"
                                            accept=".csv,.xlsx"
                                            multiple
                                            className="hidden"
                                            onChange={(e) => {
                                                const files = e.target.files
                                                if (files) {
                                                    Array.from(files).forEach((file) => {
                                                        handleFileUpload(file)
                                                    })
                                                }
                                            }}
                                        />
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() =>
                                                    fileInputRef.current?.click()
                                                }
                                                disabled={uploadingFile}
                                            >
                                                <Upload className="h-4 w-4 mr-2" />
                                                {uploadingFile
                                                    ? 'Uploading...'
                                                    : 'Upload File'}
                                            </Button>
                                        {currentConversation.uploadedFiles &&
                                            currentConversation.uploadedFiles.length > 0 && (
                                                <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                                                    <span>Uploaded files:</span>
                                                    {currentConversation.uploadedFiles.map(
                                                        (file, idx) => (
                                                            <span
                                                                key={idx}
                                                                className="px-2 py-1 bg-muted rounded"
                                                            >
                                                                📄 {file.filename}
                                                            </span>
                                                        )
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                        {/* Google Drive Download Section */}
                                        <div className="flex items-center gap-2">
                                            <div className="flex-1 flex items-center gap-2">
                                                <LinkIcon className="h-4 w-4 text-muted-foreground" />
                                                <Input
                                                    type="text"
                                                    placeholder="Paste Google Drive link here..."
                                                    value={driveUrl}
                                                    onChange={(e) =>
                                                        setDriveUrl(e.target.value)
                                                    }
                                                    onKeyDown={(e) => {
                                                        if (
                                                            e.key === 'Enter' &&
                                                            !downloadingDrive
                                                        ) {
                                                            handleGoogleDriveDownload()
                                                        }
                                                    }}
                                                    disabled={downloadingDrive}
                                                    className="flex-1"
                                                />
                                            </div>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={handleGoogleDriveDownload}
                                                disabled={
                                                    downloadingDrive ||
                                                    !driveUrl.trim()
                                                }
                                            >
                                                <Download className="h-4 w-4 mr-2" />
                                                {downloadingDrive
                                                    ? 'Downloading...'
                                                    : 'Download'}
                                            </Button>
                                        </div>
                                        {currentConversation.downloadedDocuments &&
                                            currentConversation.downloadedDocuments.length >
                                                0 && (
                                                <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                                                    <span>Documents:</span>
                                                    {currentConversation.downloadedDocuments.map(
                                                        (doc, idx) => (
                                                            <span
                                                                key={idx}
                                                                className="px-2 py-1 bg-muted rounded"
                                                            >
                                                                📄 {doc.filename}
                                                            </span>
                                                        )
                                                    )}
                                                </div>
                                            )}
                                    </div>
                                    <Chat
                                        messages={currentConversation.messages}
                                        onSendMessage={sendMessage}
                                        isLoading={isLoading}
                                        status={status}
                                    />
                                </>
                            ) : (
                                <div className="flex items-center justify-center h-full">
                                    <Button onClick={createNewConversation}>
                                        Start a new conversation
                                    </Button>
                                </div>
                            )}
                        </main>
                        {isCodeOpen && (
                            <div className="h-full border-l col-span-1 overflow-hidden">
                                <CodeSidebar />
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

export default Page
