import React from 'react'
import ReactDOM from 'react-dom/client'
import { createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { QueryClientProvider } from '@tanstack/react-query'
import '@/theme/global.css'
import { RootLayout } from './routes/__root'
import { IndexPage } from './routes/app'
import { SlotsPage } from './routes/app/slots'
import { SlotsCreateForm } from './routes/app/slots-create'
import { RecruitersPage } from './routes/app/recruiters'
import { CitiesPage } from './routes/app/cities'
import { QuestionsPage } from './routes/app/questions'
import { QuestionNewPage } from './routes/app/question-new'
import { CandidatesPage } from './routes/app/candidates'
import { DashboardPage } from './routes/app/dashboard'
import { ProfilePage } from './routes/app/profile'
import { LoginPage } from './routes/app/login'
import { CandidateDetailPage } from './routes/app/candidate-detail'
import { CandidateNewPage } from './routes/app/candidate-new'
import { RecruiterNewPage } from './routes/app/recruiter-new'
import { RecruiterEditPage } from './routes/app/recruiter-edit'
import { CityNewPage } from './routes/app/city-new'
import { CityEditPage } from './routes/app/city-edit'
import { TemplateListPage } from './routes/app/template-list'
import { TemplateNewPage } from './routes/app/template-new'
import { TemplateEditPage } from './routes/app/template-edit'
import { QuestionEditPage } from './routes/app/question-edit'
import { MessageTemplatesPage } from './routes/app/message-templates'
import { SystemPage } from './routes/app/system'
import { queryClient } from '@/api/client'

const rootRoute = createRootRoute({
  id: 'root',
  component: RootLayout,
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app',
  component: IndexPage,
})

const slotsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/slots',
  component: SlotsPage,
})

const slotsCreateRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/slots/create',
  component: SlotsCreateForm,
})

const recruitersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/recruiters',
  component: RecruitersPage,
})

const recruiterNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/recruiters/new',
  component: RecruiterNewPage,
})

const recruiterEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/recruiters/$recruiterId/edit',
  component: RecruiterEditPage,
  id: 'recruiterEdit',
})

const citiesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/cities',
  component: CitiesPage,
})

const cityNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/cities/new',
  component: CityNewPage,
})

const cityEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/cities/$cityId/edit',
  component: CityEditPage,
  id: 'cityEdit',
})

const templatesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/templates',
  component: TemplateListPage,
})

const templateNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/templates/new',
  component: TemplateNewPage,
})

const templateEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/templates/$templateId/edit',
  component: TemplateEditPage,
  id: 'templateEdit',
})

const questionsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/questions',
  component: QuestionsPage,
})

const questionNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/questions/new',
  component: QuestionNewPage,
})

const questionEditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/questions/$questionId/edit',
  component: QuestionEditPage,
  id: 'questionEdit',
})

const messageTemplatesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/message-templates',
  component: MessageTemplatesPage,
})

const systemRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/system',
  component: SystemPage,
})

const candidatesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/candidates',
  component: CandidatesPage,
})

const candidateNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/candidates/new',
  component: CandidateNewPage,
})

const candidateDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/candidates/$candidateId',
  component: CandidateDetailPage,
  id: 'candidateDetail',
})

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/app/dashboard',
  component: DashboardPage,
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
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>
)
