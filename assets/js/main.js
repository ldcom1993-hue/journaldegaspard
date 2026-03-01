const projects = [
  {
    title: "Olive et Tom",
    description: "Personnages, équipes et histoire",
    image: "https://placehold.co/800x500/e8eefc/1f2937?text=Olive+et+Tom",
    link: "/univers/olive-et-tom/",
    order: 1,
  },
  // Pour ajouter une nouvelle carte, dupliquez cet objet et ajustez:
  // - title
  // - description
  // - image
  // - link
  // - order (plus petit = affiché en premier)
];

const grid = document.querySelector("#projects-grid");
const template = document.querySelector("#project-card-template");

const sortedProjects = [...projects].sort((a, b) => a.order - b.order);

sortedProjects.forEach((project) => {
  const card = template.content.firstElementChild.cloneNode(true);
  const link = card.querySelector(".project-link");
  const image = card.querySelector(".project-image");
  const title = card.querySelector(".project-title");
  const description = card.querySelector(".project-description");

  link.href = project.link;
  image.src = project.image;
  image.alt = `Illustration de l'univers ${project.title}`;
  title.textContent = project.title;
  description.textContent = project.description;

  grid.appendChild(card);
});
