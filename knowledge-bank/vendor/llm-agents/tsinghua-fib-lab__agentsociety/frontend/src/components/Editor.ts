import { Editor as _Editor, loader } from '@monaco-editor/react'
loader.config({
    paths: {
        vs: '/monaco-editor/min/vs'
    }
})

export const Editor = _Editor
