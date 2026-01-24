import React, { Suspense, lazy } from 'react'
import ReactDOM from 'react-dom/client'
import { createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { QueryClientProvider } from '@tanstack/react-query'
import '@/theme/global.css'
import { RootLayout } from './routes/__root'
import { ErrorBoundary } from './components/ErrorBoundary'
import { queryClient } from '@/api/client'

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
const MessageTemplatesPage = lazy(() => import('./routes/app/message-templates').then(m => ({ default: m.MessageTemplatesPage })))

// Loading fallback
function PageLoader() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '200px',
      color: 'var(--muted)',
    }}>
      <div style={{
        width: '24px',
        height: '24px',
        border: '2px solid var(--glass-strong)',
        borderTopColor: 'var(--accent)',
        borderRadius: '50%',
        animation: 'spin 0.8s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

// Wrap lazy components with Suspense
function withSuspense<P extends object>(Component: React.ComponentType<P>) {
  return function SuspenseWrapper(props: P) {
    return (
      <Suspense fallback={<PageLoader />}>
        <Component {...props} />
      </Suspense>
    )
  }
}

const rootRoute = createRootRoute({
  id: 'root',
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
  id: 'recruiterEdit',
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
  id: 'cityEdit',
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
  id: 'templateEdit',
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
  id: 'questionEdit',
})

const messageTemplatesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/message-templates',
  component: withSuspense(MessageTemplatesPage),
})

const systemRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/system',
  component: SystemPage,
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
  id: 'candidateDetail',
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
  messageTemplatesRoute,
  systemRoute,
  candidatesRoute,
  candidateNewRoute,
  candidateDetailRoute,
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
