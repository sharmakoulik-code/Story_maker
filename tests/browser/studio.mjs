import { once } from 'node:events'
import { createServer } from 'node:net'
import { join } from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

export const repo = fileURLToPath(new URL('../../', import.meta.url))
const isWindows = process.platform === 'win32'
const python = process.env.KOMA_TEST_PYTHON || join(repo, '.venv', isWindows ? 'Scripts' : 'bin', isWindows ? 'python.exe' : 'python')
export const executable = process.env.KOMA_CHROMIUM_EXECUTABLE

export async function freePort() {
  const socket = createServer().listen(0, '127.0.0.1')
  await once(socket, 'listening')
  const { port } = socket.address()
  await new Promise(resolve => socket.close(resolve))
  return port
}

export async function studio(workspace, port) {
  const child = spawn(python, ['-m', 'backend', '--data-dir', workspace, '--port', String(port)], { cwd: repo, stdio: ['ignore', 'pipe', 'pipe'] })
  let output = ''
  const done = new Promise(resolve => { child.once('exit', resolve); child.once('error', resolve) })
  try {
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error(`Studio didn't start:\n${output}`)), 25_000)
      function log(data) {
        output += data.toString()
        if (output.includes('Uvicorn running on')) { clearTimeout(timeout); resolve() }
      }
      child.stdout.on('data', log)
      child.stderr.on('data', log)
      child.once('error', error => { clearTimeout(timeout); reject(error) })
      child.once('exit', code => { clearTimeout(timeout); reject(new Error(`Studio exited (${code}):\n${output}`)) })
    })
  } catch (error) { child.kill(); await done; throw error }
  return async (signal = 'SIGTERM') => { child.kill(signal); await done }
}

export async function visible(page, name) {
  await page.getByRole('heading', { name, exact: true }).waitFor()
}
