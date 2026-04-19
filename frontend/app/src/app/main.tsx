import React, { Suspense, lazy } from 'react'
import ReactDOM from 'react-dom/client'
import { createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { QueryClientProvider } from '@tanstack/react-query'
import '@/theme/global.css'
import { RootLayout } from './routes/__root'
import { ErrorBoundary } from './components/ErrorBoundary'
import { PageLoader } from './components/AppStates'
import { queryClient } from '@/api/client'

if (import.meta.env.PROD && typeof window !== 'undefined') {
  const reloadKey = 'spa_chunk_reload'
  window.addEventListener('vite:preloadError', () => {
    if (sessionStorage.getItem(reloadKey) === '1') {
      return
    }
    sessionStorage.setItem(reloadKey, '1')
    window.location.reload()
  })
  window.addEventListener('load', () => {
    sessionStorage.removeItem(reloadKey)
  })
}

// Lightweight pages - load eagerly
import { IndexPage } from './routes/app'
import { LoginPage } from './routes/app/login'
import { ProfilePage } from './routes/app/profile'
import { SystemPage } from './routes/app/system'

// Heavy pages - lazy load
const DashboardPage = lazy(() => import('./routes/app/dashboard').then(m => ({ default: m.DashboardPage })))
const CandidatesPage = lazy(() => import('./routes/app/candidates').then(m => ({ default: m.CandidatesPage })))
const CandidateDetailPage = lazy(() => import('./routes/app/candidate-detail').then(m => ({ default: m.CandidateDetailPage })))
const CandidateNewPage = lazy(() => import('./routes/app/candidate-new').then(m => ({ default: m.CandidateNewPage })))
const SlotsPage = lazy(() => import('./routes/app/slots').then(m => ({ default: m.SlotsPage })))
const SlotsCreateForm = lazy(() => import('./routes/app/slots-create').then(m => ({ default: m.SlotsCreateForm })))
const RecruitersPage = lazy(() => import('./routes/app/recruiters').then(m => ({ default: m.RecruitersPage })))
const RecruiterNewPage = lazy(() => import('./routes/app/recruiter-new').then(m => ({ default: m.RecruiterNewPage })))
const RecruiterEditPage = lazy(() => import('./routes/app/recruiter-edit').then(m => ({ default: m.RecruiterEditPage })))
const CitiesPage = lazy(() => import('./routes/app/cities').then(m => ({ default: m.CitiesPage })))
const CityNewPage = lazy(() => import('./routes/app/city-new').then(m => ({ default: m.CityNewPage })))
const CityEditPage = lazy(() => import('./routes/app/city-edit').then(m => ({ default: m.CityEditPage })))
const TemplateListPage = lazy(() => import('./routes/app/template-list').then(m => ({ default: m.TemplateListPage })))
const TemplateNewPage = lazy(() => import('./routes/app/template-new').then(m => ({ default: m.TemplateNewPage })))
const TemplateEditPage = lazy(() => import('./routes/app/template-edit').then(m => ({ default: m.TemplateEditPage })))
const QuestionsPage = lazy(() => import('./routes/app/questions').then(m => ({ default: m.QuestionsPage })))
const QuestionNewPage = lazy(() => import('./routes/app/question-new').then(m => ({ default: m.QuestionNewPage })))
const QuestionEditPage = lazy(() => import('./routes/app/question-edit').then(m => ({ default: m.QuestionEditPage })))
const TestBuilderPage = lazy(() => import('./routes/app/test-builder').then(m => ({ default: m.TestBuilderPage })))
const TestBuilderGraphPage = lazy(() => import('./routes/app/test-builder-graph').then(m => ({ default: m.TestBuilderGraphPage })))
const MessageTemplatesPage = lazy(() => import('./routes/app/message-templates').then(m => ({ default: m.MessageTemplatesPage })))
const MessengerPage = lazy(() => import('./routes/app/messenger').then(m => ({ default: m.MessengerPage })))
const CalendarPage = lazy(() => import('./routes/app/calendar').then(m => ({ default: m.CalendarPage })))
const IncomingPage = lazy(() => import('./routes/app/incoming').then(m => ({ default: m.IncomingPage })))
const SimulatorPage = lazy(() => import('./routes/app/simulator').then(m => ({ default: m.SimulatorPage })))
// Telegram Mini App pages (lazy)
const TgAppLayout = lazy(() => import('./routes/tg-app/layout').then(m => ({ default: m.TgAppLayout })))
const TgDashboardPage = lazy(() => import('./routes/tg-app/index').then(m => ({ default: m.TgDashboardPage })))
const TgIncomingPage = lazy(() => import('./routes/tg-app/incoming').then(m => ({ default: m.TgIncomingPage })))
const TgCandidatePage = lazy(() => import('./routes/tg-app/candidate').then(m => ({ default: m.TgCandidatePage })))
const MaxMiniAppPage = lazy(() => import('./routes/miniapp').then(m => ({ default: m.MaxMiniAppPage })))

// Wrap lazy components with Suspense
function withSuspense<P extends object>(Component: React.ComponentType<P>) {
  return function SuspenseWrapper(props: P) {
    return (
      <Suspense fallback={<PageLoader compact description="Открываем рабочий экран." />}>
        <Component {...props} />
      </Suspense>
    )
  }
}

const rootRoute = createRootRoute({
  component: RootLayout,
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app',
  component: IndexPage,
})

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/dashboard',
  component: withSuspense(DashboardPage),
})

const profileRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/profile',
  component: ProfilePage,
})

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/login',
  component: LoginPage,
})

const slotsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/slots',
  component: withSuspense(SlotsPage),
})

const slotsCreateRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/slots/create',
  component: withSuspense(SlotsCreateForm),
})

const recruitersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/recruiters',
  component: withSuspense(RecruitersPage),
})

const recruiterNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/recruiters/new',
  component: withSuspense(RecruiterNewPage),
})

const recruiterEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/recruiters/$recruiterId/edit',
  component: withSuspense(RecruiterEditPage),
})

const citiesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/cities',
  component: withSuspense(CitiesPage),
})

const cityNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/cities/new',
  component: withSuspense(CityNewPage),
})

const cityEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/cities/$cityId/edit',
  component: withSuspense(CityEditPage),
})

const templatesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/templates',
  component: withSuspense(TemplateListPage),
})

const templateNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/templates/new',
  component: withSuspense(TemplateNewPage),
})

const templateEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/templates/$templateId/edit',
  component: withSuspense(TemplateEditPage),
})

const questionsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/questions',
  component: withSuspense(QuestionsPage),
})

const questionNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/questions/new',
  component: withSuspense(QuestionNewPage),
})

const questionEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/questions/$questionId/edit',
  component: withSuspense(QuestionEditPage),
})

const testBuilderRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/test-builder',
  component: withSuspense(TestBuilderPage),
})

const testBuilderGraphRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/test-builder/graph',
  component: withSuspense(TestBuilderGraphPage),
})

const messageTemplatesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/message-templates',
  component: withSuspense(MessageTemplatesPage),
})

const messengerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/messenger',
  component: withSuspense(MessengerPage),
})

const calendarRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/calendar',
  component: withSuspense(CalendarPage),
})

const incomingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/incoming',
  component: withSuspense(IncomingPage),
})

const systemRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/system',
  component: SystemPage,
})

const simulatorRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/simulator',
  component: withSuspense(SimulatorPage),
})

const candidatesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/candidates',
  component: withSuspense(CandidatesPage),
})

const candidateNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/candidates/new',
  component: withSuspense(CandidateNewPage),
})

const candidateDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/candidates/$candidateId',
  component: withSuspense(CandidateDetailPage),
})

// Telegram Mini App routes
const tgAppLayoutRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'tg-app-layout',
  component: withSuspense(TgAppLayout),
})

const tgDashboardRoute = createRoute({
  getParentRoute: () => tgAppLayoutRoute,
  path: '/tg-app',
  component: withSuspense(TgDashboardPage),
})

const tgIncomingRoute = createRoute({
  getParentRoute: () => tgAppLayoutRoute,
  path: '/tg-app/incoming',
  component: withSuspense(TgIncomingPage),
})

const tgCandidateRoute = createRoute({
  getParentRoute: () => tgAppLayoutRoute,
  path: '/tg-app/candidates/$candidateId',
  component: withSuspense(TgCandidatePage),
})

const maxMiniAppRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/miniapp',
  component: withSuspense(MaxMiniAppPage),
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  dashboardRoute,
  profileRoute,
  loginRoute,
  slotsRoute,
  slotsCreateRoute,
  recruitersRoute,
  recruiterNewRoute,
  recruiterEditRoute,
  citiesRoute,
  cityNewRoute,
  cityEditRoute,
  templatesRoute,
  templateNewRoute,
  templateEditRoute,
  questionsRoute,
  questionNewRoute,
  questionEditRoute,
  testBuilderRoute,
  testBuilderGraphRoute,
  messageTemplatesRoute,
  messengerRoute,
  calendarRoute,
  incomingRoute,
  systemRoute,
  simulatorRoute,
  candidatesRoute,
  candidateNewRoute,
  candidateDetailRoute,
  maxMiniAppRoute,
  tgAppLayoutRoute.addChildren([
    tgDashboardRoute,
    tgIncomingRoute,
    tgCandidateRoute,
  ]),
])
const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>
)
