const { InstanceBase, runEntrypoint } = require('@companion-module/base')

class DuopusModule extends InstanceBase {
  constructor(internal) {
    super(internal)
    this.pollTimer = null
    this._destroyed = false
    this.lastSnap = null
    this.lastVmix = null
  }

  getConfigFields() {
    return [
      {
        type: 'textinput',
        id: 'duopus_url',
        label: 'Duopus URL',
        tooltip: 'Base URL, e.g. http://192.168.1.10',
        width: 12,
        default: 'http://127.0.0.1',
      },
    ]
  }

  get baseUrl() {
    return (this.config.duopus_url || '').replace(/\/$/, '')
  }

  async destroy() {
    this._destroyed = true
    if (this.pollTimer) clearTimeout(this.pollTimer)
    this.pollTimer = null
  }

  async requestJson(path, options = {}) {
    const ctrl = new AbortController()
    const t = setTimeout(() => ctrl.abort(), 2000)
    let res
    try {
      res = await fetch(`${this.baseUrl}${path}`, {
        ...options,
        signal: ctrl.signal,
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      })
    } finally {
      clearTimeout(t)
    }
    if (!res.ok) {
      const t = await res.text()
      throw new Error(`${res.status} ${t}`)
    }
    if (res.status === 204) return null
    return await res.json()
  }

  fmt(totalSec) {
    const s = Math.max(0, Math.floor(Number(totalSec) || 0))
    const m = Math.floor(s / 60)
    const r = s % 60
    return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`
  }

  async poll() {
    try {
      this.lastSnap = await this.requestJson('/api/rundown/active')
      this.lastVmix = await this.requestJson('/api/vmix/state')
    } catch (e) {
      this.log('debug', `poll: ${e.message}`)
      return
    }
    if (!this.lastSnap) return
    const live = this.lastSnap?.live_story
    const elapsed = this.lastSnap?.elapsed_seconds || 0
    const planned = live?.planned_duration || 0
    const rem = Math.max(0, planned - elapsed)
    this.setVariableValues({
      current_story: live?.title || '',
      elapsed: this.fmt(elapsed),
      remaining: this.fmt(rem),
    })
    this.checkFeedbacks('story_live')
    this.checkFeedbacks('tally_state')
  }

  async init() {
    this.setVariableDefinitions([
      { variableId: 'current_story', name: 'Current story title' },
      { variableId: 'elapsed', name: 'Elapsed (MM:SS)' },
      { variableId: 'remaining', name: 'Remaining (MM:SS)' },
    ])

    this.setActionDefinitions({
      advance_rundown: {
        name: 'Next (sub-story + story + vMix)',
        options: [],
        callback: async () => {
          await this.requestJson('/api/rundown/next', { method: 'POST' })
        },
      },
      go_live: {
        name: 'Go live (Cut)',
        options: [
          {
            id: 'input',
            type: 'number',
            label: 'vMix input',
            default: 1,
            min: 1,
            max: 1000,
          },
        ],
        callback: async (event) => {
          const input = Number(event.options.input)
          await this.requestJson('/api/vmix/command', {
            method: 'POST',
            body: JSON.stringify({ function: 'Cut', input }),
          })
        },
      },
      go_to_story: {
        name: 'Go to story',
        options: [
          {
            id: 'story_id',
            type: 'textinput',
            label: 'Story UUID',
            tooltip: 'Copy from Duopus rundown UI (story id)',
            default: '',
          },
        ],
        callback: async (event) => {
          const storyId = String(event.options.story_id || '').trim()
          if (!storyId) return
          await this.requestJson('/api/rundown/go_to_story', {
            method: 'POST',
            body: JSON.stringify({ story_id: storyId }),
          })
        },
      },
      set_prompter_speed: {
        name: 'Prompter speed',
        options: [
          {
            id: 'delta',
            type: 'dropdown',
            label: 'Delta',
            choices: [
              { id: '1', label: 'Faster (+1)' },
              { id: '-1', label: 'Slower (-1)' },
            ],
            default: '1',
          },
        ],
        callback: async (event) => {
          const delta = Number(event.options.delta)
          await this.requestJson('/api/prompter/speed', {
            method: 'POST',
            body: JSON.stringify({ delta }),
          })
        },
      },
    })

    this.setFeedbackDefinitions({
      story_live: {
        type: 'boolean',
        name: 'Story is live',
        description: 'True when the given story UUID is on air',
        options: [
          {
            id: 'story_id',
            type: 'textinput',
            label: 'Story UUID',
            default: '',
          },
        ],
        defaultStyle: {
          bgcolor: 0x330000,
          color: 0xffffff,
        },
        callback: async (feedback) => {
          const want = String(feedback.options.story_id || '').trim()
          const liveId = this.lastSnap?.live_story?.id
          return Boolean(want && liveId && want === liveId)
        },
      },
      tally_state: {
        type: 'advanced',
        name: 'vMix tally (input)',
        description: 'Red = program, green = preview',
        options: [
          {
            id: 'input',
            type: 'number',
            label: 'vMix input',
            default: 1,
            min: 1,
            max: 1000,
          },
        ],
        callback: async (feedback) => {
          const input = Number(feedback.options.input)
          const tally = this.lastVmix?.tally
          const by = tally?.by_input || {}
          const st = by[String(input)]
          let bgcolor = 0x222222
          if (st === 1) bgcolor = 0xaa0000
          else if (st === 2) bgcolor = 0x00aa00
          return { bgcolor }
        },
      },
    })

    const tick = async () => {
      try {
        await this.poll()
      } catch (e) {
        this.log('error', e.message)
      }
      if (!this._destroyed) this.pollTimer = setTimeout(tick, 1000)
    }
    tick()
  }
}

runEntrypoint(DuopusModule, [])
