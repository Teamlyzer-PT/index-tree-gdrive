# drive-tree

Indice automatico do Google Drive da empresa, atualizado a cada hora no GitHub Pages.

---

## Setup (10 minutos, so fazes uma vez)

### Passo 1: Google Cloud Console

1. Abre https://console.cloud.google.com
2. Cria um projeto novo (ou usa um que ja tenhas)
3. No menu lateral, vai a **APIs & Services > Library**
4. Pesquisa "Google Drive API" e clica **Enable**
5. No menu lateral, vai a **IAM & Admin > Service Accounts**
6. Clica **Create Service Account**
   - Nome: `drive-tree`
   - Os outros campos podes saltar, clica **Done**
7. Na lista, clica no email que acabou de aparecer (tipo `drive-tree@projeto.iam.gserviceaccount.com`)
8. Vai ao separador **Keys**
9. Clica **Add Key > Create new key > JSON > Create**
10. Vai fazer download de um ficheiro `.json`. Guarda-o, vais precisar ja a seguir.

### Passo 2: Partilhar a pasta do Drive

1. Abre o Google Drive no browser
2. Vai a pasta que queres indexar
3. Olha para o URL. Vai ser algo como:
   `https://drive.google.com/drive/folders/1aBcDeFgHiJkLmNoPqRsT`
   O ID da pasta e a parte depois de `folders/` (neste exemplo: `1aBcDeFgHiJkLmNoPqRsT`).
   **Copia esse ID.**
4. Clica com o botao direito na pasta > **Partilhar**
5. No campo de email, cola o email da service account (o tal `drive-tree@projeto.iam.gserviceaccount.com`)
6. Permissao: **Leitor**
7. Clica **Enviar**

### Passo 3: GitHub

1. Vai a https://github.com/new e cria um repo novo (pode ser privado)
2. Faz upload de todos os ficheiros deste projeto para o repo (generate.py, requirements.txt, .github/workflows/deploy.yml)
3. Vai a **Settings > Secrets and variables > Actions**
4. Clica **New repository secret** e cria estes dois:

   | Nome                       | Valor                                                    |
   |----------------------------|----------------------------------------------------------|
   | `GOOGLE_CREDENTIALS_JSON`  | Abre o ficheiro .json do Passo 1 num editor de texto, seleciona TUDO, e cola aqui |
   | `DRIVE_FOLDER_ID`          | O ID da pasta que copiaste no Passo 2                    |

5. (Opcional) Em **Variables** (no mesmo sitio), cria:

   | Nome            | Valor                     |
   |-----------------|---------------------------|
   | `COMPANY_NAME`  | O nome da tua empresa     |

6. Vai a **Settings > Pages**
7. Em **Source**, seleciona **GitHub Actions**

### Passo 4: Correr pela primeira vez

1. Vai ao separador **Actions** do repo
2. Do lado esquerdo, clica em **Atualizar Drive Tree**
3. Clica no botao **Run workflow > Run workflow**
4. Espera uns 30 segundos
5. O teu site fica em: `https://TEU-USERNAME.github.io/NOME-DO-REPO/`

Partilha esse link com os colaboradores. Pronto, acabou.

---

## Perguntas rapidas

**Com que frequencia atualiza?**
De hora a hora. Se quiseres mudar, edita o ficheiro `.github/workflows/deploy.yml` e muda o `cron`.

**Custa alguma coisa?**
Nao. GitHub Pages e gratis, Google Cloud com service account para leitura e gratis.

**E se alguem adicionar ficheiros ao Drive?**
Aparecem automaticamente na proxima atualizacao (no maximo 1 hora depois).

**Posso forcar uma atualizacao?**
Sim, vai a Actions > Atualizar Drive Tree > Run workflow.
