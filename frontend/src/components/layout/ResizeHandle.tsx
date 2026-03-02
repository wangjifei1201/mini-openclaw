'use client'

import { useState, useCallback, useEffect } from 'react'

interface ResizeHandleProps {
  onResize: (delta: number) => void
  direction?: 'left' | 'right'
}

export default function ResizeHandle({ onResize, direction = 'right' }: ResizeHandleProps) {
  const [isDragging, setIsDragging] = useState(false)
  
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])
  
  useEffect(() => {
    if (!isDragging) return
    
    let lastX = 0
    
    const handleMouseMove = (e: MouseEvent) => {
      if (lastX === 0) {
        lastX = e.clientX
        return
      }
      
      const delta = direction === 'right' ? e.clientX - lastX : lastX - e.clientX
      lastX = e.clientX
      onResize(delta)
    }
    
    const handleMouseUp = () => {
      setIsDragging(false)
    }
    
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, onResize, direction])
  
  return (
    <div
      onMouseDown={handleMouseDown}
      className={`resize-handle ${isDragging ? 'bg-klein-blue' : ''}`}
      style={{ cursor: 'col-resize' }}
    />
  )
}
