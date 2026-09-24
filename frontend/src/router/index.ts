import { createRouter, createWebHistory } from "vue-router";
import { getToken } from "../api/session";
import AppShell from "../components/AppShell.vue";
import LoginView from "../views/LoginView.vue";
import WorkspaceView from "../views/WorkspaceView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView },
    {
      path: "/",
      component: AppShell,
      meta: { requiresAuth: true },
      children: [
        { path: "", redirect: "/inbox" },
        {
          path: "inbox/:id?",
          name: "inbox",
          component: WorkspaceView,
        },
        { path: "assistant", redirect: "/inbox" },
        { path: "tools", redirect: "/inbox" },
      ],
    },
  ],
});

router.beforeEach((to) => {
  const loggedIn = Boolean(getToken());
  if (to.matched.some((record) => record.meta.requiresAuth) && !loggedIn) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.name === "login" && loggedIn) {
    return { path: "/inbox" };
  }
  return true;
});

export default router;
