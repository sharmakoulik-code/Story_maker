import '@fontsource-variable/dm-sans/wght.css'
import '@fontsource-variable/fraunces/wght.css'
import '@fontsource-variable/fraunces/wght-italic.css'
import './studio.css'
import './planning.css'
import './visuals.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { CharactersPage } from './Characters'
import { StoryboardPage } from './Storyboard'
import { Dashboard } from './Dashboard'
import { StoryPlanPage } from './PlanWorkspace'
import { ProjectLibrary } from './Projects'
import { NewStory, StoryProject } from './Story'
import { SystemSettings } from './Settings'
import { MissingPage, StudioShell } from './ui'

const router = createBrowserRouter([{
  element: <StudioShell />,
  children: [
    { index: true, element: <Dashboard /> },
    { path: 'new', element: <NewStory /> },
    { path: 'projects', element: <ProjectLibrary /> },
    { path: 'characters', element: <CharactersPage /> },
    { path: 'projects/:id/storyboard', element: <StoryboardPage /> },
    { path: 'projects/:id/plan', element: <StoryPlanPage /> },
    { path: 'projects/:id', element: <StoryProject /> },
    { path: 'settings', element: <SystemSettings /> },
    { path: '*', element: <MissingPage /> },
  ],
}])

createRoot(document.getElementById('root')!).render(<StrictMode><RouterProvider router={router} /></StrictMode>)
