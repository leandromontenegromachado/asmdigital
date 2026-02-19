import { Connector } from './types';

export const INITIAL_CONNECTORS: Connector[] = [
  {
    id: 'redmine',
    name: 'Redmine',
    description: 'Gestão de projetos e rastreamento de issues.',
    logoUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuAOA-Ku2pJnqI-zFvyJgy0G1nAhtviNe5_8Lhs_ii1LCmFFl5881PPaD6dYjiIv482-X_ek3zi6xvDqP6Cjv8avSvW-O-5BK9rRy7KN_XEgRhJ_0pJi9_eMdi-dqG5b2j6CsHnQA4qR3yEmvjWVQIcf2OnO7gyU5etmlzOMgqu68NDXelAVlupfa_jVgbTOMAlsXXHkbJo93-6GyqJ4d10SgyezHktdw9MZAeMRZiw_gcSkbT_k5H6Xn4JlLi1Emy-a7Ld0uKWVDO0',
    logoAlt: 'Redmine Logo',
    status: 'connected',
    syncTime: '12 min atrás'
  },
  {
    id: 'azure-devops',
    name: 'Azure DevOps',
    description: 'Build, test, and deploy with CI/CD.',
    logoUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBg0qoLaqqvfGSo1HhJLz0jc9LT_Nx2jbPjdmc0idn96w_6jGJomddFRNptlEveFcrYuEnpnpt64Rk0ktuV9DF0I0awHVDxq-5UfhJ74GT_FZsgz2vMsS-_3OOCQxyR9i75JzDdimq6qZf_YcOOENWMVWU39TiyO7_Po3zuMcbIwwpMVFTUR4av_GU2x_gAI8L6RR6I3g23Cnx_hhxHKUXr3vxyGL7n7Ml4BcNUkhSDENowlfUcctskZGl1s7vvJCZ9ZK_cMWpYEVs',
    logoAlt: 'Azure DevOps Logo',
    status: 'editing', // Default to expanded for demo purposes matching the screenshot
    config: {
      urlLabel: 'URL da Organização',
      urlValue: 'https://dev.azure.com/my-tech-org',
      tokenLabel: 'Personal Access Token (PAT)',
      tokenValue: 'xk3490fk304fk3049fk3049fk',
      projectLabel: 'Projeto Padrão',
      projectValue: 'Automation Platform MVP',
      projects: ['Automation Platform MVP', 'Legacy Systems', 'Internal Tools'],
      warning: 'A conexão atual está ativa, mas alguns endpoints retornaram timeout. Verifique suas permissões de rede.'
    }
  },
  {
    id: 'fadpro',
    name: 'FADPRO',
    description: 'Fundação de Apoio e Desenvolvimento.',
    logoUrl: '', // Will use text placeholder if empty or special handling
    logoAlt: 'FADPRO',
    status: 'error',
    errorMessage: 'Falha na autenticação',
    errorCode: '401'
  },
  {
    id: 'msteams',
    name: 'Microsoft Teams',
    description: 'Notificações e alertas em canais de equipe.',
    logoUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuACz0HpwacV0IQcQzQXldx5HDpt1Nr_KZ5nhkAU7ZS2Pqj8cjEL4rOpegyYL57wISK6ZvIAwsDyy1tuMVs3eZ7wmHP-XcEbWAYIlT1eCtZbmYHG6qN_vLmFTHtwn0x_P6BrRphLZOa1aBwlB_6ZAprhjRIq1oDi6ZNpDgR5lYiOt5aJLD4TDn4ABfwP9mzBaDPJG810qmgS-WeA3jrXkxja_5ed6A5oAbJC79CS9vOMvZb9LChA9XyVsW_eBtloUnK1jt8GdN3Nn6E',
    logoAlt: 'Teams Logo',
    status: 'inactive'
  },
  {
    id: 'slack',
    name: 'Slack',
    description: 'Colaboração e bots de automação.',
    logoUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBQzJbfgwcPtoAvuaLWInXEi_oHdXc6bbb6ZrtSawPUAdH7niJkalJ186-uxmsYqJ2b48fouJb0J-NMOX_SyF93KbAJAsZP6xHND_WvXHzE9Xk0b9KvqhEL4vZVX0hyG3wJtjCH0YmC7bqrtQMW6cRkT4JsokZRfgezKBSKP0KcnqKTI2GLpe6l4glNLAJQWbXy9zeUeYLDjLBCjl6lsyCRccrBXyNK1iBbWBPcltO69pVaZUzLVJUKShQZ0oUhUDsAoeU-7hKcFPk',
    logoAlt: 'Slack Logo',
    status: 'inactive'
  },
  {
    id: 'jira',
    name: 'Jira Software',
    description: 'Rastreamento de projetos ágeis.',
    logoUrl: 'https://lh3.googleusercontent.com/aida-public/AB6AXuD8Zkdq7MXR17vOUCJFx4uKYnVz87obYjTYmN-td7r12-sEZmYcJR1G0TLwiHVUHOVMG6ZVjwvdpVsrnmrjbBIg4lVLDM9iXFblGDgTa3IexF_NI5owvSFEK7vQId6-l_m4wtrLK7eRiwR78ZdBuyXsxxQ4S7Z0mdn22LrxiDtoJNiUriLCJeIvfQVXh5BQYHDitBIlxYbyFm2bUE_xJIycJ0slvGk2FIN6d1AnbfN3niGUJ43_UWBajsX_CzeS4eR_eEe7gDhSQrc',
    logoAlt: 'Jira Logo',
    status: 'inactive'
  }
];
