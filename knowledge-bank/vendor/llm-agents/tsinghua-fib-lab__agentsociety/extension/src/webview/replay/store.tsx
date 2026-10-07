import * as React from 'react';
import type {
  AgentProfile,
  ExperimentInfo,
  InitData,
  LayoutMode,
  PlaybackState,
  ReplayAgentStateAtStep,
  ReplayDatasetRows,
  ReplayEnvStateAtStep,
  ReplayPanelSchema,
  ReplayPosition,
  TimelinePoint,
} from './types';

/** Replay store state */
export interface ReplayState {
  initialized: boolean;
  loading: boolean;
  error: string | null;

  initData: InitData | null;
  experimentInfo: ExperimentInfo | null;
  panelSchema: ReplayPanelSchema | null;

  timeline: TimelinePoint[];
  currentStep: number;
  playback: PlaybackState;
  layoutMode: LayoutMode;

  agentProfiles: Map<number, AgentProfile>;
  positionsAtStep: ReplayPosition[];
  agentStateRowsAtStep: Record<string, ReplayAgentStateAtStep>;
  envStateRowsAtStep: Record<string, ReplayEnvStateAtStep>;

  selectedAgentId: number | null;
  selectedAgentHistoryDatasetId: string | null;
  replayDatasetRowsByRequestKey: Record<string, ReplayDatasetRows | null>;
}

/** Replay store actions */
export interface ReplayActions {
  setInitData: (data: InitData) => void;
  setExperimentInfo: (info: ExperimentInfo) => void;
  setPanelSchema: (schema: ReplayPanelSchema) => void;
  setTimeline: (timeline: TimelinePoint[]) => void;
  setAgentProfiles: (profiles: AgentProfile[]) => void;
  setStepBundle: (bundle: {
    layout_hint: LayoutMode;
    positions: ReplayPosition[];
    agent_state_rows: Record<string, ReplayAgentStateAtStep>;
    env_state_rows: Record<string, ReplayEnvStateAtStep>;
  }) => void;
  setCurrentStep: (step: number) => void;
  selectAgent: (agentId: number | null) => void;
  setSelectedAgentHistoryDatasetId: (datasetId: string | null) => void;
  setReplayDatasetRows: (requestKey: string, rows: ReplayDatasetRows | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setInitialized: (initialized: boolean) => void;
  play: () => void;
  pause: () => void;
  nextStep: () => void;
  prevStep: () => void;
  setPlaybackSpeed: (speed: number) => void;
}

const initialState: ReplayState = {
  initialized: false,
  loading: true,
  error: null,
  initData: null,
  experimentInfo: null,
  panelSchema: null,
  timeline: [],
  currentStep: 0,
  playback: {
    isPlaying: false,
    speed: 1000,
    currentStep: 0,
  },
  layoutMode: 'random',
  agentProfiles: new Map(),
  positionsAtStep: [],
  agentStateRowsAtStep: {},
  envStateRowsAtStep: {},
  selectedAgentId: null,
  selectedAgentHistoryDatasetId: null,
  replayDatasetRowsByRequestKey: {},
};

/** Combined context type */
export interface ReplayContextType {
  state: ReplayState;
  actions: ReplayActions;
  sendMessage: (message: any) => void;
}

const ReplayContext = React.createContext<ReplayContextType | null>(null);

export interface ReplayProviderProps {
  children: React.ReactNode;
  vscode: any;
}

export const ReplayProvider: React.FC<ReplayProviderProps> = ({ children, vscode }) => {
  const [state, setState] = React.useState<ReplayState>(initialState);
  const playbackTimerRef = React.useRef<NodeJS.Timeout | null>(null);

  const actions: ReplayActions = React.useMemo(() => ({
    setInitData: (data) => setState((s) => ({ ...s, initData: data })),

    setExperimentInfo: (info) => setState((s) => ({ ...s, experimentInfo: info })),

    setPanelSchema: (schema) =>
      setState((s) => ({
        ...s,
        panelSchema: schema,
        layoutMode: schema.layout_hint ?? s.layoutMode,
        selectedAgentHistoryDatasetId:
          s.selectedAgentHistoryDatasetId ?? schema.primary_agent_state_dataset_id ?? null,
      })),

    setTimeline: (timeline) => setState((s) => ({ ...s, timeline })),

    setAgentProfiles: (profiles) => {
      const map = new Map<number, AgentProfile>();
      profiles.forEach((profile) => map.set(profile.id, profile));
      setState((s) => ({ ...s, agentProfiles: map }));
    },

    setStepBundle: (bundle) =>
      setState((s) => ({
        ...s,
        layoutMode: bundle.layout_hint ?? s.layoutMode,
        positionsAtStep: bundle.positions ?? [],
        agentStateRowsAtStep: bundle.agent_state_rows ?? {},
        envStateRowsAtStep: bundle.env_state_rows ?? {},
      })),

    setCurrentStep: (step) =>
      setState((s) => ({
        ...s,
        currentStep: step,
        playback: { ...s.playback, currentStep: step },
      })),

    selectAgent: (agentId) =>
      setState((s) => ({
        ...s,
        selectedAgentId: agentId,
        selectedAgentHistoryDatasetId:
          agentId === null
            ? s.selectedAgentHistoryDatasetId
            : s.panelSchema?.primary_agent_state_dataset_id ?? s.selectedAgentHistoryDatasetId,
      })),

    setSelectedAgentHistoryDatasetId: (datasetId) =>
      setState((s) => ({
        ...s,
        selectedAgentHistoryDatasetId: datasetId,
      })),

    setReplayDatasetRows: (requestKey, rows) =>
      setState((s) => ({
        ...s,
        replayDatasetRowsByRequestKey: {
          ...s.replayDatasetRowsByRequestKey,
          [requestKey]: rows,
        },
      })),

    setLoading: (loading) => setState((s) => ({ ...s, loading })),

    setError: (error) => setState((s) => ({ ...s, error })),

    setInitialized: (initialized) => setState((s) => ({ ...s, initialized })),

    play: () => {
      setState((s) => ({
        ...s,
        playback: { ...s.playback, isPlaying: true },
      }));
    },

    pause: () => {
      setState((s) => ({
        ...s,
        playback: { ...s.playback, isPlaying: false },
      }));
    },

    nextStep: () => {
      setState((s) => {
        const nextIdx = Math.min(s.currentStep + 1, s.timeline.length - 1);
        return {
          ...s,
          currentStep: nextIdx,
          playback: { ...s.playback, currentStep: nextIdx },
        };
      });
    },

    prevStep: () => {
      setState((s) => {
        const prevIdx = Math.max(s.currentStep - 1, 0);
        return {
          ...s,
          currentStep: prevIdx,
          playback: { ...s.playback, currentStep: prevIdx },
        };
      });
    },

    setPlaybackSpeed: (speed) =>
      setState((s) => ({
        ...s,
        playback: { ...s.playback, speed },
      })),
  }), []);

  React.useEffect(() => {
    if (state.playback.isPlaying) {
      playbackTimerRef.current = setInterval(() => {
        setState((s) => {
          const nextIdx = s.currentStep + 1;
          if (nextIdx >= s.timeline.length) {
            return {
              ...s,
              playback: { ...s.playback, isPlaying: false },
            };
          }
          return {
            ...s,
            currentStep: nextIdx,
            playback: { ...s.playback, currentStep: nextIdx },
          };
        });
      }, state.playback.speed);
    } else if (playbackTimerRef.current) {
      clearInterval(playbackTimerRef.current);
      playbackTimerRef.current = null;
    }

    return () => {
      if (playbackTimerRef.current) {
        clearInterval(playbackTimerRef.current);
      }
    };
  }, [state.playback.isPlaying, state.playback.speed]);

  const sendMessage = React.useCallback((message: any) => {
    vscode.postMessage(message);
  }, [vscode]);

  const contextValue = React.useMemo(
    () => ({ state, actions, sendMessage }),
    [state, actions, sendMessage]
  );

  return (
    <ReplayContext.Provider value={contextValue}>
      {children}
    </ReplayContext.Provider>
  );
};

export const useReplay = (): ReplayContextType => {
  const context = React.useContext(ReplayContext);
  if (!context) {
    throw new Error('useReplay must be used within a ReplayProvider');
  }
  return context;
};
