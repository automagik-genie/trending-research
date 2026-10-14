// Cordis owns this reader only. Accepted evidence remains in native Brain.
import { spawn } from 'node:child_process'
import { createInterface } from 'node:readline'

export async function apply(ctx, config) {
  const child = spawn('python3', ['-B', '-m', 'observatory.evidence', 'serve'], {
    cwd: config.cwd,
    env: { PATH: process.env.PATH, LANG: 'C.UTF-8' },
    stdio: ['pipe', 'pipe', 'ignore'],
  })
  let active = true
  let sequence = 0
  const pending = new Map()
  let readyResolve, readyReject
  const ready = new Promise((resolve, reject) => { readyResolve = resolve; readyReject = reject })
  const exited = new Promise(resolve => child.once('exit', (code, signal) => resolve({ code, signal })))
  const lines = createInterface({ input: child.stdout })
  const fail = error => {
    readyReject(error)
    for (const request of pending.values()) request.reject(error)
    pending.clear()
  }
  child.once('error', fail)
  child.once('exit', () => fail(new Error('Evidence reader exited')))
  lines.on('line', line => {
    try {
      const message = JSON.parse(line)
      if (message.ready === true) readyResolve()
      else {
        const request = pending.get(message.id)
        if (!request) return fail(new Error('Unexpected reader response'))
        pending.delete(message.id)
        request.resolve(message.result)
      }
    } catch { fail(new Error('Invalid evidence reader response')) }
  })
  ctx.effect(() => async () => {
    active = false
    fail(new Error('Evidence plugin disposed'))
    child.stdin.end()
    let timer
    const result = await Promise.race([
      exited,
      new Promise(resolve => { timer = setTimeout(() => { child.kill('SIGTERM'); resolve(null) }, 5000) }),
    ])
    clearTimeout(timer)
    lines.close()
    if (!result || result.code !== 0 || result.signal) {
      child.kill('SIGKILL')
      throw new Error('Evidence reader cleanup failed')
    }
  })
  child.stdin.write(JSON.stringify({ binding: config.binding, scene_id: config.scene_id }) + '\n')
  let timer
  try {
    await Promise.race([ready, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('Evidence reader startup timed out')), 30000)
    })])
  } finally { clearTimeout(timer) }
  config.onReady(Object.freeze({
    request(action, edge_id) {
      if (!active) return Promise.reject(new Error('Evidence plugin disposed'))
      const id = ++sequence
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject })
        child.stdin.write(JSON.stringify({ id, action, ...(edge_id === undefined ? {} : { edge_id }) }) + '\n')
      })
    },
  }))
}
