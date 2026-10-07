import { makeAutoObservable, runInAction } from "mobx";
import { Agent, AgentDialog, AgentProfile, AgentStatus, AgentSurvey, LngLat, Time, ApiMetric } from "./components/type";
import { message } from "antd";
import React from "react";
import { Experiment, Survey } from "../../components/type";
import { round4 } from "../../components/util";
import { fetchCustom } from "../../components/fetch";

const formatStatus = (status: unknown): string | number => {
    if (typeof status === 'number') {
        return round4(status)
    } else if (typeof status === 'string') {
        if (status == "") {
            return '-'
        }
        return status
    } else if (status === undefined || status === null) {
        return '-'
    } else if (typeof status === 'object') {
        if (Array.isArray(status)) {
            return JSON.stringify(status.map(s => formatStatus(s)))
        }
        return JSON.stringify(status)
    }
    return String(status)
}

export class ReplayStore {
    mapCenter: LngLat = {
        lng: 116.39124329043085,
        lat: 39.906120097057055,
    }
    mapCenterDone = false // 是否已经根据agent位置设置了mapCenter

    expID?: string
    experiment?: Experiment
    _timeline: Time[] = []
    _currentTime?: Time = undefined
    _agent2Profile: Map<number, AgentProfile> = new Map()
    globalPrompt?: string = undefined
    agents: Map<number, Agent> = new Map()
    clickedAgentID?: number = undefined
    _clickedAgentStatuses: AgentStatus[] = []
    _clickedAgentDialogs: AgentDialog[] = []
    _clickedAgentSurveys: AgentSurvey[] = []
    _metrics: Map<string, ApiMetric[]> = new Map()

    _id2surveys: Map<string, Survey> = new Map()

    heatmapKeyInStatus?: string = undefined

    constructor() {
        makeAutoObservable(this)
    }

    setCenter(center: LngLat) {
        this.mapCenter = center
    }

    setHeatmapKeyInStatus(key?: string) {
        console.log('set heatmap key: ', key)
        this.heatmapKeyInStatus = key
    }

    get timeline() {
        return this._timeline?.slice() ?? []
    }

    async _fetchSurveys() {
        try {
            const res = await fetchCustom('/api/surveys')
            const data = await res.json()
            runInAction(() => {
                const surveys = data.data as Survey[]
                this._id2surveys = new Map(surveys.map(s => [s.id, s]))
            })
        } catch (err) {
            message.error(`Failed to fetch surveys: ${JSON.stringify(err)}`, 3);
            console.error('Failed to fetch surveys: ', err);
        }
    }

    async _fetchExperiment() {
        if (this.expID === undefined) {
            return
        }
        try {
            const res = await fetchCustom(`/api/experiments/${this.expID}`)
            const data = await res.json()
            runInAction(() => {
                this.experiment = data.data as Experiment
            })
            {
                const res = await fetchCustom(`/api/experiments/${this.expID}/timeline`)
                const data = await res.json()
                runInAction(() => {
                    this._timeline = data.data as Time[]
                    if (this.experiment?.status === 2) {
                        // completed -> set currentTime to the last time
                        this._currentTime = this._timeline[this._timeline.length - 1]
                    } else if (this.experiment?.status === 1) {
                        // running -> set currentTime to the first time
                        this._currentTime = this._timeline[0]
                    }
                })
                if (this._timeline.length === 0) {
                    throw "bad experiment with no timeline"
                }
            }
        } catch (err) {
            message.error(`Failed to fetch experiment: ${JSON.stringify(err)}`, 3);
            console.error('Failed to fetch experiment: ', err);
        }
    }

    async _fetchAgentProfile() {
        if (this.expID === undefined) {
            return
        }
        try {
            const res = await fetchCustom(`/api/experiments/${this.expID}/agents/-/profile`)
            const data = await res.json()
            runInAction(() => {
                this._agent2Profile = new Map((data.data as AgentProfile[]).map(a => {
                    a.profile = Object.fromEntries(Object.entries(a.profile).map(([k, v]) => [k, formatStatus(v)]))
                    return [a.id, a]
                })
                )
            })
        } catch (err) {
            message.error(`Failed to fetch agent profile: ${JSON.stringify(err)}`, 3);
            console.error('Failed to fetch agent profile: ', err);
        }
    }

    async _fetchAllAgentStatusAndPrompt(time?: Time) {
        if (this.expID === undefined) {
            return
        }
        try {
            let url = `/api/experiments/${this.expID}/agents/-/status`
            if (time !== undefined) {
                url += `?day=${time.day}&t=${time.t}`
            }
            const res = await fetchCustom(url)
            const data = await res.json()
            const agentStatuses = data.data as AgentStatus[]
            // if (agentStatuses.length > 0) {
            //     console.log('fetched agent status: ', agentStatuses.length)
            // }
            runInAction(() => {
                const center = {
                    lng: 0,
                    lat: 0,
                }
                let cnt = 0
                const newAgents = new Map<number, Agent>()
                // merge status with profile
                agentStatuses.forEach((status) => {
                    if (!this.mapCenterDone) {
                        if (status.lng !== undefined && status.lng !== null && status.lat !== undefined && status.lat !== null) {
                            center.lng += status.lng
                            center.lat += status.lat
                            cnt += 1
                            console.log('status: ', JSON.stringify(status))
                            console.log('center: ', JSON.stringify(center))
                            console.log('cnt: ', cnt)
                            console.log('mean: ', center.lng / cnt, center.lat / cnt)
                        }
                    }
                    if (typeof status.status === 'object' && status.status !== null) {
                        status.status = Object.fromEntries(Object.entries(status.status).map(([k, v]) => [k, formatStatus(v)]))
                    }
                    // 如果status是字符串，直接保持原样
                    const profile = this._agent2Profile.get(status.id)
                    if (profile !== undefined) {
                        newAgents.set(status.id, { ...profile, ...status })
                    } else {
                        console.error('agent profile not found: ', status.id)
                    }
                })
                this.agents = newAgents
                if (cnt > 0 && !this.mapCenterDone) {
                    center.lng /= cnt
                    center.lat /= cnt
                    this.mapCenter = center
                    console.log('set center: ', JSON.stringify(center))
                    this.mapCenterDone = true
                }
            })
        } catch (err) {
            message.error(`Failed to fetch data: ${JSON.stringify(err)}`, 3);
            console.error('Failed to fetch data: ', err);
        }
        try {
            let url = `/api/experiments/${this.expID}/prompt`
            if (time !== undefined) {
                url += `?day=${time.day}&t=${time.t}`
            }
            const res = await fetchCustom(url)
            let prompt = undefined
            if (res.ok) {
                const data = await res.json()
                if (data.data !== undefined && data.data !== null) {
                    prompt = data.data.prompt
                }
            }
            runInAction(() => {
                this.globalPrompt = prompt
            })
        } catch (err) {
            // message.error(`Failed to fetch prompt: ${JSON.stringify(err)}`, 3);
            console.error('Failed to fetch prompt: ', err);
        }
    }

    async _fetchClickedAgent() {
        if (this.expID === undefined || this.clickedAgentID === undefined) {
            return
        }
        try {
            {
                const res = await fetchCustom(`/api/experiments/${this.expID}/agents/${this.clickedAgentID}/status`)
                const data = await res.json()
                for (const status of data.data as AgentStatus[]) {
                    if (typeof status.status === 'object' && status.status !== null) {
                        status.status = Object.fromEntries(Object.entries(status.status).map(([k, v]) => [k, formatStatus(v)]))
                    }
                    // 如果status是字符串，直接保持原样
                }
                runInAction(() => {
                    this._clickedAgentStatuses = data.data as AgentStatus[]
                })
            }
            {
                const res = await fetchCustom(`/api/experiments/${this.expID}/agents/${this.clickedAgentID}/dialog`)
                const data = await res.json()
                runInAction(() => {
                    this._clickedAgentDialogs = data.data as AgentDialog[]
                })
            }
            {
                const res = await fetchCustom(`/api/experiments/${this.expID}/agents/${this.clickedAgentID}/survey`)
                const data = await res.json()
                runInAction(() => {
                    this._clickedAgentSurveys = data.data as AgentSurvey[]
                })
            }
        } catch (err) {
            message.error(`Failed to fetch agent: ${JSON.stringify(err)}`, 3);
            console.error('Failed to fetch agent: ', err);
        }
    }

    async _fetchMetrics() {
        if (this.expID === undefined) {
            return
        }
        try {
            const res = await fetchCustom(`/api/experiments/${this.expID}/metrics`)
            const data = await res.json()
            runInAction(() => {
                // Handle null or undefined data.data
                if (data.data && typeof data.data === 'object') {
                    this._metrics = new Map(Object.entries(data.data))
                } else {
                    this._metrics = new Map()
                }
            })
        } catch (err) {
            message.error(`Failed to fetch metrics: ${JSON.stringify(err)}`, 3);
            console.error('Failed to fetch metrics: ', err);
        }
    }

    get metrics() {
        return this._metrics
    }

    async init(expID?: string) {
        message.loading({
            key: "loading",
            content: `Loading experiment ${expID} ...`
        }, 0)
        this.mapCenterDone = false
        await this._fetchSurveys()
        this.expID = expID
        this.clickedAgentID = undefined
        this._clickedAgentStatuses = []
        if (expID === undefined) {
            this._timeline = []
            this._agent2Profile = new Map()
            this.agents = new Map()
            this._metrics = new Map()
        } else {
            await this._fetchExperiment()
            await this._fetchAgentProfile()
            await this._fetchMetrics()
            if (this.experiment?.status === 2) {
                // completed -> fetch the newest data
                await this._fetchAllAgentStatusAndPrompt(this._currentTime)
            } else if (this.experiment?.status === 1) {
                // running -> fetch the newest data
                await this._fetchAllAgentStatusAndPrompt()
            }
        }
        message.destroy("loading")
    }

    async fetchByTime(time: Time) {
        if (this.expID === undefined) {
            return
        }
        this._currentTime = time
        await this._fetchAllAgentStatusAndPrompt(time)
        await this._fetchClickedAgent()
        await this._fetchMetrics()
    }

    // 获取最新的experiment数据，刷新所有数据，如果有clickedAgentID，也刷新clickedAgentID的数据
    async refresh() {
        // 1. 刷新experiment数据
        await this._fetchExperiment()
        // 2. 刷新所有agent数据
        await this._fetchAllAgentStatusAndPrompt(this._currentTime)
        // 3. 刷新clickedAgent数据
        await this._fetchClickedAgent()
        // 4. 刷新metrics数据
        await this._fetchMetrics()
    }

    async setClickedAgentID(agentID?: number) {
        this.clickedAgentID = agentID
        this._clickedAgentStatuses = []
        if (agentID === undefined) {
            return
        }
        await this._fetchClickedAgent()
    }

    get currentTime() {
        return this._currentTime
    }

    get id2surveys() {
        return this._id2surveys
    }

    get clickedAgent() {
        if (this.clickedAgentID === undefined) {
            return undefined
        }
        const a = this.agents.get(this.clickedAgentID)
        if (a === undefined) {
            return undefined
        }
        return { ...a }
    }

    get clickedAgentStatuses() {
        if (this._currentTime === undefined) {
            return []
        }
        if (this._clickedAgentStatuses === undefined) {
            return []
        }
        // filter by current time
        return this._clickedAgentStatuses.slice().filter(s => (s.day < this._currentTime!.day || s.day === this._currentTime!.day && s.t <= this._currentTime!.t))
    }

    get clickedAgentDialogs() {
        if (this._currentTime === undefined) {
            return []
        }
        if (this._clickedAgentDialogs === undefined) {
            return []
        }
        // filter by current time
        return this._clickedAgentDialogs.slice().filter(d => d.day < this._currentTime!.day || d.day === this._currentTime!.day && d.t <= this._currentTime!.t)
    }

    get clickedAgentSurveys() {
        if (this._currentTime === undefined) {
            return []
        }
        if (this._clickedAgentSurveys === undefined) {
            return []
        }
        // filter by current time
        return this._clickedAgentSurveys.slice().filter(s => s.day < this._currentTime!.day || s.day === this._currentTime!.day && s.t <= this._currentTime!.t)
    }
}

export const store = new ReplayStore()
export const StoreContext = React.createContext(store)
