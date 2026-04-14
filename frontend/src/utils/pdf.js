const PDF_MIMETYPE = 'application/pdf'

export function parseFilename(disposition, fallback) {
  if (!disposition) {
    return fallback
  }

  const utfMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utfMatch?.[1]) {
    try {
      return decodeURIComponent(utfMatch[1])
    } catch {
      return utfMatch[1]
    }
  }

  const simpleMatch = disposition.match(/filename="?([^"]+)"?/i)
  return simpleMatch?.[1] || fallback
}

function downloadBlob(blob, filename) {
  if (window.navigator?.msSaveOrOpenBlob) {
    window.navigator.msSaveOrOpenBlob(blob, filename)
    return
  }

  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  anchor.style.display = 'none'
  document.body.appendChild(anchor)

  try {
    anchor.click()
  } catch {
    window.open(url, '_blank', 'noopener,noreferrer')
  } finally {
    window.setTimeout(() => {
      anchor.remove()
      URL.revokeObjectURL(url)
    }, 1500)
  }
}

export function triggerPdfDownload(path) {
  const separator = path.includes('?') ? '&' : '?'
  const iframe = document.createElement('iframe')
  iframe.style.display = 'none'
  iframe.src = `${path}${separator}download_ts=${Date.now()}`
  document.body.appendChild(iframe)
  window.setTimeout(() => {
    iframe.remove()
  }, 60000)
}

async function extractErrorMessage(blob, fallback) {
  try {
    const text = await blob.text()
    if (!text) {
      return fallback
    }

    try {
      const parsed = JSON.parse(text)
      // Handle both {error: "message"} and {message: "message"} formats
      return parsed?.error || parsed?.message || fallback
    } catch {
      // If not JSON, return first 240 chars of text (could be HTML error page)
      const message = text.slice(0, 240).trim()
      return message || fallback
    }
  } catch {
    return fallback
  }
}

function looksLikePdf(contentType, bytes) {
  if (String(contentType || '').toLowerCase().includes('pdf')) {
    return true
  }

  const signature = new TextDecoder('ascii').decode(bytes.slice(0, 5))
  return signature === '%PDF-'
}

export async function savePdfResponse(response, fallbackName) {
  console.log('[PDF] savePdfResponse called with response:', {
    status: response.status,
    headers: response.headers,
    dataType: response.data?.constructor?.name,
    dataSize: response.data?.size,
  })
  
  // Check HTTP status code
  if ((response.status || 200) >= 400) {
    console.log('[PDF] Error status detected:', response.status)
    const contentType = response.headers?.['content-type'] || ''
    const blob =
      response.data instanceof Blob
        ? response.data
        : new Blob([response.data], { type: contentType || 'application/json' })
    const message = await extractErrorMessage(blob, 'Failed to download PDF report.')
    console.log('[PDF] Error message extracted:', message)
    throw new Error(message)
  }

  const contentType = response.headers?.['content-type'] || ''
  console.log('[PDF] Content-Type from headers:', contentType)
  
  // Handle Blob or Array response
  let blob = response.data
  if (!(blob instanceof Blob)) {
    console.log('[PDF] Response data is not a Blob, converting...')
    blob = new Blob([response.data], { type: contentType || PDF_MIMETYPE })
  }

  const buffer = await blob.arrayBuffer()
  const bytes = new Uint8Array(buffer)
  
  console.log('[PDF] Response content-type:', contentType)
  console.log('[PDF] Response size:', bytes.length, 'bytes')
  console.log('[PDF] Response first 5 bytes:', Array.from(bytes.slice(0, 5)))
  console.log('[PDF] Response signature:', String.fromCharCode(...bytes.slice(0, 5)))
  
  // Verify we actually got a PDF
  if (!looksLikePdf(contentType, bytes)) {
    console.log('[PDF] Response does not look like a PDF')
    // Try to extract error message from the response
    const message = await extractErrorMessage(blob, 'Failed to download PDF report.')
    console.log('[PDF] Error message:', message)
    throw new Error(message)
  }

  const payload = new Blob([buffer], { type: PDF_MIMETYPE })
  const filename = parseFilename(
    response.headers?.['content-disposition'],
    fallbackName,
  )
  console.log('[PDF] Downloading as:', filename)
  downloadBlob(payload, filename)
  return filename
}
