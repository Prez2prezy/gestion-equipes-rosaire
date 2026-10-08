"""
MA DIZAINE AU QUOTIDIEN — Données et calcul des mystères du Rosaire.
Portage FIDÈLE de l'application Android (© MOTIAN TOFFÉ Ahua Innocent) :
- Les 20 mystères (textes, références, intentions, fruits, clausules)
- La règle de calcul jour/mois/numéro (conversion exacte des formules VBA/Excel)

Règle métier : chaque membre d'équipe a un numéro 1-20 ; selon la date du jour,
il médite le(s) mystère(s) déterminé(s) par sa position dans la chaîne.
Les 20 membres couvrent ensemble le chapelet complet chaque jour.
"""

from database import c

# Couleurs par type de mystère (palette du livre, harmonisée gestionnaire)
COULEURS_TYPES = {
    "joyeux": "#E91E63",
    "lumineux": "#3F51B5",
    "douloureux": "#880E4F",
    "glorieux": "#388E3C",
    "autre": "#9E9E9E",
}

MYSTERES = [
    {
        "id": 1, "titre": "L'ANNONCIATION", "reference": "Luc 1, 28 - 38", "type": "Joyeux",
        "passage": "L'Ange entra chez Marie et dit: «Je te salue Comblée-de-grâce, le Seigneur est avec toi.» A cette parole; elle fut toute bouleversée, et elle se demandait ce que pouvait signifier cette salutation.\nL'ange lui dit alors: «Sois sans crainte, Marie, car tu as trouvé grâce auprès de Dieu. Voici que tu vas concevoir et enfanter un fils; tu lui donneras le nom de Jésus. Il sera grand, il sera appelé Fils du Très-Haut; le Seigneur Dieu lui donnera le trône de David son père ; il régnera pour toujours sur la maison de Jacob, et son règne n'aura pas de fin.»\nMarie dit à l'ange: «Comment cela va-t-il se faire puisque je ne connais pas d'homme?»\nL'ange lui répondit: «L'Esprit Saint viendra sur toi, et la puissance du Très-Haut te prendra sous son ombre ; c'est pourquoi celui qui va naître sera saint, il sera appelé Fils de Dieu. Or voici que, dans sa vieillesse, Élisabeth, ta parente, a conçu, elle aussi, un fils et en est à son sixième mois, alors qu'on l'appelait la femme stérile. Car rien n'est impossible à Dieu.»\nMarie dit alors: «Voici la servante du Seigneur ; que tout m'advienne selon ta parole!» Et l'ange la quitta.\n",
        "meditation": "La salutation de l'ange bouleverse Marie. L'ange comprend son trouble. Il la rassure et lui annonce la mission que Dieu veut lui confier.\nLe dialogue s'installe entre eux et c'est librement que Marie va consentir à faire la volonté de Dieu",
        "intentions": "pour les enfants qui meurent dans le sein maternel et pour leur maman,\npour les couples qui ne peuvent pas avoir d'enfant,\npour ceux qui n'osent pas croire que Dieu a un projet d'amour pour eux,\nIntention du prochain dans la chaine de prière,",
        "fruits": "L'adhésion à la volonté de Dieu,\nL'humilité.",
        "clausules": ["annoncé par l'ange,", "le Fils du Très - Haut,", "annoncé par les prophètes,", "le Sauveur du monde,", "l'Envoyé du père,", "le messie attendu par Israël,", "vrai Dieu et vrai homme,", "dont la venue bouleverse vos projets,", "qui vient faire sa demeure en vous,", "qui veut naître en nos cœurs,"]
    },
    {
        "id": 2, "titre": "LA VISITATION", "reference": "Luc 1, 39 - 47", "type": "Joyeux",
        "passage": "En ces jours-là, Marie partit et se rendit en hâte vers la région montagneuse, dans une ville de Juda. Elle entra chez Zacharie et salua Élisabeth. \nOr, quand Elisabeth entendit la salutation de Marie, l'enfant tressaillit en elle. Alors, Elisabeth fut remplit d'Esprit Saint, s'écria d'une voix forte: « Tu es bénie entre toutes les femmes, et le fruit de tes entrailles est béni. D'où m'est-il donné que la mère de mon Seigneur vienne jusqu'à moi? Car, lorsque tes paroles de salutation sont parvenues à mes oreilles, l'enfant a tressailli d'allégresse en moi. Heureuse celle qui a cru à l'accomplissement des paroles qui lui furent dites de la part du Seigneur.»\nMarie dit alors: «Mon âme exalte le Seigneur, exulte mon esprit en Dieu mon Sauveur...»\n",
        "meditation": "Sur la parole de l'ange, Marie part en toute hâte se mettre au service d'Elisabeth. Remplie de l'Esprit Saint, celle-ci lui confirme qu'elle porte en son sein le Fils du Très-Haut.\nJean-Baptiste tressaille. La joie se communique et la foi grandit dans le cœur des deux femmes.\nEt Marie loue Dieu : Magnificat!",
        "intentions": "pour les futures mamans,\npour ceux qui attendent de nous un service ou une aide,\npour que nous sachions ouvrir notre cœur et notre maison à ceux qui ont besoin d'aide,\nIntention du prochain dans la chaine de prière,",
        "fruits": "La Charité fraternelle,\nLe service du prochain.",
        "clausules": ["reconnu comme Seigneur par Elisabeth,", "Enfant de la promesse,", "qui inaugure les temps nouveaux,", "Rédempteur et Sauveur,", "qui apporte la joie,", "qui s'est fait Serviteur,", "qui nous commande l'amour du prochain,", "notre guide dans la foi,", "qui transforme toute vie,", "qui s'invite dans nos maisons,"]
    },
    {
        "id": 3, "titre": "LA NATIVITÉ", "reference": "Luc 2, 7 - 14", "type": "Joyeux",
        "passage": "Marie mit au monde son fils premier-né; elle l'emmaillota et le coucha dans une mangeoire, car il n'y avait pas de place pour eux dans la salle commune.\nDans la même région, il y avait des bergers qui vivaient dehors et passaient la nuit dans les champs pour garder leurs troupeaux.\nL'Ange du Seigneur se présenta devant eux, et la gloire du Seigneur les enveloppa de sa lumière. Ils furent saisis d'une grande crainte.\nAlors l'ange leur dit: «Ne craignez pas, car voici que je vous annonce une bonne nouvelle, qui sera une grande joie pour tout le peuple: aujourd'hui, dans la ville de David, vous est né un Sauveur qui est le Christ, le Seigneur. Et voici le signe qui vous est donné: vous trouverez un nouveau-né emmailloté et couché dans une mangeoire.»\n",
        "meditation": "Voici que Marie met au monde son fils. Qu'importe la pauvreté du lieu, un même amour unit Joseph, Marie et l'enfant.\nLes bergers reçoivent la visite de l'ange. Ce sont les premiers témoins d'un Dieu qui s'est fait pauvre et petit pour attirer à lui tous les petits de la terre.",
        "intentions": "pour que cessent en tout pays l'exploitation et la maltraitance des enfants,\npour que ceux qui vivent par choix la pauvreté évangélique afin de rejoindre leurs frères les plus pauvres,\npour que notre cœur devienne la demeure de Dieu en qu'en Lui nous trouvions la vraie richesse,\nIntention du prochain dans la chaine de prière,",
        "fruits": "La joie,\nLa Paix,\nL'Esprit de pauvreté.",
        "clausules": ["qui se fait petit enfant,", "enveloppé et couché dans une mangeoire,", "Fils de David,", "Verbe fait chair,", "Emmanuel, Dieu avec nous,", "dont la venue sur terre réjouit tout le ciel,", "Pauvre parmi les pauvres,", "Roi d'humilité,", "venu annoncer la Paix aux hommes,", "vers qui montent toutes nos louanges,"]
    },
    {
        "id": 4, "titre": "LA PRÉSENTATION AU TEMPLE", "reference": "Luc 2, 27 - 35", "type": "Joyeux",
        "passage": "Sous l'action de l'Esprit, Syméon vint donc au Temple. Au moment où les parents présentaient l'enfant Jésus pour se conformer au rite de la Loi qui le concernait, Syméon reçut l'Enfant dans ses bras, et il bénit Dieu et dit: « Maintenant, ô Maître souverain, tu peux laisser ton serviteur s'en aller en paix, selon ta parole. Car mes yeux ont vu le salut que tu préparais à la face des peuples: lumière qui se revèle aux nations et donne gloire à ton peuple Israël.» [...]\nSyméon les bénit, puis dit à Marie, sa mère: «Voici que cet enfant provoquera la chute et le relèvement de beaucoup en Israël. Il sera un signe de contradiction. Et toi, ton âme sera traversée d'un glaive.»\n",
        "meditation": "Syméon porte l'enfant et bénit Dieu. Rempli de l'Esprit, il parle au nom du Seigneur. Son annonce est à la fois positive et joyeuse mais aussi grave et tragique.\nMarie sera étroitement unie à la Passion de son fils",
        "intentions": "pour que nos cœurs reconnaissent Jésus comme la lumière qui dissipe les ténèbres,\npour ceux qui attendent de voir le Salut de Dieu,\npour les personnes consacrées qui portent le monde dans leur prière,\nIntention du prochain dans la chaine de prière,",
        "fruits": "L'obéissance,\nL'offrande de soi,\nLa pureté du cœur.",
        "clausules": ["présenté au temple,", "le Messie attendu,", "Lumière pour éclairer les nations,", "Consolation et gloire d'Israël,", "Soleil levant venu nous visiter,", "Salut pour tous les peuples,", "le Chemin, la Vérité, la Vie,", "venu apporter la Paix,", "rempli de sagesse,", "qui nous fait passer des ténèbres à la lumière,"]
    },
    {
        "id": 5, "titre": "LE RECOUVREMENT AU TEMPLE", "reference": "Luc 2, 46 - 51", "type": "Joyeux",
        "passage": "C'est au bout de trois jours que Marie et Joseph trouvèrent Jésus dans le Temple, assis au milieu des docteurs de la Loi: il les écoutait et leur posait des questions, et tous ceux qui l'entendaient s'extasiaient sur son intelligence et sur ses réponses.\nEn le voyant, ses parents furent frappés d'étonnement, et sa mère lui dit: «Mon enfant, pourquoi nous as-tu fait cela? Vois comme ton père et moi, nous avons souffert en te cherchant!» \nIl leur dit: «Comment se fait-il que vous m'ayez cherché? Ne saviez-vous pas qu'il me faut être chez mon Père?»\nMais ils ne comprirent pas ce qu'il leur disait. Il descendit avec eux pour se rendre à Nazareth, et il leur était soumis. Sa mère gardait en son cœur tous ces événements.\n",
        "meditation": "Grande est l'inquiètude de Joseph et de Marie. Jésus s'en étonne. Où trouver Jésus sinon occupé aux affaires de son Père!\nA leur tour, ils ne comprennent pas. Jésus révèle son identité de Fils de Dieu.\nMarie et Joseph continuent leur chemin de foi.",
        "intentions": "pour les adolescents en souffrance,\npour les parents et les éducateurs,\npour que nous soyons des chercheurs de Dieu, attentifs à sa présence,\nIntention du prochain dans la chaine de prière,",
        "fruits": "La recherche de Dieu.",
        "clausules": ["perdu et retrouvé,", "rempli de sagesse et d'intelligence,", "le Fils Bien-aimé du Père,", "rempli de zèle pour la gloire de Dieu son Père,", "Parole vivante du Père,", "venu accomplir la volonté de son Père,", "qui a vécu caché à Nazareth,", "qui nous apprend à chercher le Royaume,", "qui se laisse trouver par ceux qui le cherchent,", "joie des cœurs simples,"]
    },
    {
        "id": 6, "titre": "LE BAPTÊME AU JOURDAIN", "reference": "Luc 3, 21 - 22", "type": "Lumineux",
        "passage": "Comme tout le peuple se faisait baptiser et qu'après avoir été baptisé lui aussi, Jésus priait, le ciel s'ouvrit. L'Esprit Saint, sous une apparence corporelle, comme une colombe, descendit sur Jésus, et il y eut une voix venant du ciel: «Toi, tu es mon Fils Bien-aimé; en toi, je trouve ma joie.»\n",
        "meditation": "Au premier jour de la création, la voix de Dieu a retenti pour faire surgir le monde du néant. C'est cette même voix qui, au jour de son baptême par Jean dans le Jourdain, retentit depuis le ciel et désigne Jésus comme le Fils bien-aimé du Père.\nVenu s'associer aux pécheurs appelés à la conversion, Jésus est investi dans sa mission de Fils pour être le Sauveur du monde.",
        "intentions": "pour ceux qui se préparent au baptême,\npour que les baptisés vivent dans la fidélité à leur baptême,\npour que nous ravivions sans cesse la grâce de notre baptême,\npour ceux qui sont appelés à une mission dans l'Église,\nIntention du prochain dans la chaine de prière,",
        "fruits": "La grâce filiale.",
        "clausules": ["qui vient se faire baptiser par Jean,", "qui descend dans les eaux du Jourdain,", "qui est en prière,", "sur qui repose l'Esprit,", "qui n'a pas connu le péché,", "qui se fait solidaire des pécheurs,", "qui est désigné comme Fils,", "Fils engendré par le Père,", "l'Agneau de Dieu,", "le Sauveur du monde,"]
    },
    {
        "id": 7, "titre": "LES NOCES DE CANA", "reference": "Jean 2, 1 - 11", "type": "Lumineux",
        "passage": "Il y eut un mariage à Cana de Galilée. La mère de Jésus était là. Jésus aussi avait été invité au mariage avec ses disciples.\nOr, on manqua de vin. La mère de Jésus lui dit: «Ils n'ont pas de vin.» [...]\nSa mère dit à ceux qui servaient: «Tout ce qu'il vous dira, faites-le».\nOr, il y avait là six jarres de pierre pour les purifications rituelles des Juifs; chacune contenait deux à trois mesures, (c'est-à-dire environ cent litres). Jésus dit à ceux qui servaient: «Remplissez d'eau ces jarres.» Et ils les remplirent jusqu'au bord.\nIl leur dit: «Maintenant, puisez, et portez-en au maître du repas.\nCelui-ci goûta l'eau changée en vin. [...]\nTel fut le commencement des signes que Jésus accomplit. C'était à Cana de Galilée. Il manifesta sa gloire et ses disciples crurent en lui.\n",
        "meditation": "Pour que la fête ne soit pas gâchée si le vin venait à manquer, Marie intervient auprès de Jésus.\nCette eau changée en vin est le symbole de la joie des noces que le Christ vient célébrer avec l'humanité.",
        "intentions": "pour les fiancés,\npour que les familles chrétiennes témoignent de leur amour,\npour que nous sachions faire ce que le Christ nous demande,\npour que nous soyons attentifs aux difficultés dans les familles,\nIntention du prochain dans la chaine de prière,",
        "fruits": "La confiance en Dieu.",
        "clausules": ["qui est invité aux noces,", "qui partage la joie des hommes,", "qui attend son heure,", "qui se laisse interpeller,", "qui commande aux serviteurs,", "qui change l'eau en vin,", "qui apporte le vin de la joie,", "qui est attentif aux besoins des hommes,", "qui accomplit son premier signe,", "qui manifeste sa gloire,"]
    },
    {
        "id": 8, "titre": "L'ANNONCE DU ROYAUME", "reference": "Luc 4, 16 - 21", "type": "Lumineux",
        "passage": "Jésus vint à Nazareth, où il avait été élevé. Selon son habitude, il entra dans la synagogue le jour du sabbat, et se leva pour faire la lecture.\nOn lui remit le livre du prophète Isaïe. Il ouvrit le livre et trouva le passage où il est écrit: L'Esprit du Seigneur est sur moi, parce que le Seigneur m'a consacré par l'onction.\nIl m'a envoyé porter la Bonne Nouvelle aux pauvres, annoncer aux captifs leur libération, et aux aveugles qu'ils retrouveront la vue, remettre en liberté les opprimés, annoncer une année favorable accordée par le Seigneur.\nJésus referma le livre, le rendit au servant et s'assit.\nTous, dans la synagogue, avaient les yeux fixés sur lui.\nAlors il se met à leur dire: «Aujourd'hui s'accomplit ce passage de l'Écriture que vous venez d'entendre.»\n",
        "meditation": "La Bonne Nouvelle que Jésus vient annoncer est celle-là même que le prophète Isaïe avait proclamée en son temps. En lui, s'accomplit la Parole car il est lui-même la Parole, le Verbe de Dieu venu dans la chair pour inaugurer le Royaume.",
        "intentions": "pour que l'Église soit fidèle à l'Evangile,\npour que notre cœur s'ouvre à la Parole de Dieu,\npour que les chrétiens annoncent à temps et à contretemps la Bonne Nouvelle,\npour que nous croyions à la miséricorde de Dieu pour tous les hommes,\nIntention du prochain dans la chaine de prière,",
        "fruits": "La conversion du cœur,\nL'écoute de la Parole.",
        "clausules": ["qui a été consacré par l'onction,", "qui ouvre le livre d'Isaïe,", "qui accomplit la prophétie,", "qui apporte la bonne nouvelle aux pauvres,", "qui donne la liberté aux prisonniers,", "qui donne la lumière aux aveugles,", "qui apporte la libération aux opprimés,", "qui annonce le royaume,", "qui proclame les Béatitudes,", "qui parle avec sagesse et autorité,"]
    },
    {
        "id": 9, "titre": "LA TRANSFIGURATION", "reference": "Matthieu 17, 1 - 5", "type": "Lumineux",
        "passage": "Jésus prend avec lui Pierre, Jacques et Jean son frère, et il les emmène à l'écart, sur une haute montagne.\nIl fut transfiguré devant eux; son visage devint brillant comme le soleil, et ses vêtements, blancs comme la lumière. Voici que leur apparurent Moïse et Élie, qui s'entretenaient avec lui.\nPierre alors prit la parole et dit à Jésus: «Seigneur, il est bon que nous soyons ici! Si tu le veux, je vais dresser ici trois tentes, une pour toi, une pour Moïse, et une pour Élie.»\nIl parlait encore, lorsqu'une nuée lumineuse les couvrit de son ombre, et voici que, de la nuée, une voix disait: «Celui-ci est mon Fils Bien-aimé, en qui je trouve ma joie: écoutez-le!»\n",
        "meditation": "Jésus choisit Pierre, Jacques et Jean pour être les témoins privilégiés de son Mystère.\nLa Transfiguration leur révèle la divinité de Jésus. Il est le Fils bien-aimé du Père et la Lumière du monde.",
        "intentions": "pour que le Nom du Christ soit glorifié,\npour que la Parole du Christ soit entendue,\npour ceux qui ont la charge de transmettre la foi,\npour que la Parole de Dieu prenne de plus en plus de place dans nos vies,\nIntention du prochain dans la chaine de prière,",
        "fruits": "La contemplation,\nL'union à Dieu.",
        "clausules": ["qui prend avec Lui Pierre, Jacques et Jean,", "qui monte sur une haute montagne,", "qui est transfiguré,", "dont le visage est brillant comme le soleil,", "dont les vêtements sont blancs comme la lumière,", "que les Apôtres contemplent,", "entouré de Moïse et d'Elie,", "qui est désigné comme le Fils Bien-Aimé du Père,", "en qui le Père a mis tout son amour,", "que le Père nous demande d'écouter,"]
    },
    {
        "id": 10, "titre": "L'INSTITUTION DE L'EUCHARISTIE", "reference": "Matthieu 26, 17 ; 20; 26 - 29", "type": "Lumineux",
        "passage": "Le premier jour de la fête des pains sans levain, les disciples s'approchèrent et dirent à Jésus: «Où veux-tu que nous te fassions les préparatifs pour manger la Pâque?» [...]\nLe soir venu, Jésus se trouvait à table avec les Douze. [...]\nPendant le repas, Jésus avait pris du pain prononcé la bénédiction, le rompit et, le donnant aux disciples, il dit: «Prenez, mangez: ceci est mon corps.»\nPuis, ayant pris une coupe ayant rendu grâce, il la leur donna en disant: «Buvez-en tous, car ceci est mon sang, le sang de l'Alliance, versé pour la multitude en rémission des péchés.\nJe vous le dis: desormais je ne boirai plus de ce produit de la vigne, jusqu'au jour où je le boirai, nouveau, avec vous dans le Royaume de mon Père.»\n",
        "meditation": "Ce dernier repas que Jésus veut partager avec ses disciples n'est pas un simple repas.\nC'est son repas pascal dans lequel il donne sa vie, son corps et son sang pour la multitude des péchés.",
        "intentions": "pour que les chrétiens aiment leur prochain comme Jésus nous a aimés,\npour ceux qui donnent leur vie pour les autres,\npour l'unité de l'Église, Corps du Christ,\npour que notre cœur s'ouvre au don de l'Eucharistie,\nIntention du prochain dans la chaine de prière,",
        "fruits": "L'action de grâce,\nLa communion avec le Christ dans l'Eucharistie.",
        "clausules": ["qui célèbre son repas pascal,", "qui est à table avec les Douze,", "qui prononce la bénédiction sur le pain,", "qui fait de ce pain son Corps,", "qui prononce l'action de grâce sur la coupe,", "qui fait de ce vin son Sang,", "qui donne sa vie pour tous les hommes,", "qui donne sa vie pour le pardon des péchés,", "qui va bientôt être livré,", "qui nous invite à boire le vin nouveau dans le royaume,"]
    },
    {
        "id": 11, "titre": "L'AGONIE DE JÉSUS", "reference": "Marc 14, 33 - 38", "type": "Douloureux",
        "passage": "Jésus emmène avec lui Pierre, Jacques et Jean, et commence à ressentir frayeur et angoisse. Il leur dit: «Mon âme est triste à en mourir. Restez ici et veillez.»\nAllant un peu plus loin, il tombait à terre et priait pour que, s'il était possible, cette heure s'éloigne de lui. Il disait: «Abba ... Père, tout t'est possible. Éloigne de moi cette coupe. Cependant, non pas ce que moi, je veux, mais ce que toi, tu veux !»\nPuis il revient et trouve les disciples endormis. Il dit à Pierre: «Simon, tu dors! Tu n'as pas eu la force de veiller seulement une heure ?\nVeillez et priez, pour ne pas entrer en tentation.» \n",
        "meditation": "Dans une grande solitude, Jésus traverse la nuit de l'angoisse.\nMais il désire, comme le Père, réaliser le Salut du monde en libérant l'homme captif de la mort.\nPar sa vie donnée, Jésus paie au mal et à la mort la rançon qu'ils réclament.",
        "intentions": "pour ceux qui vivent dans l'isolement et l'angoisse,\npour ceux qui subissent la trahison,\npour ceux qui désespèrent à cause d'épreuves trop lourdes,\npour que notre cœur s'ouvre à la détresse de nos frères,\nIntention du prochain dans la chaine de prière,",
        "fruits": "Le regret de nos fautes,\nLe repentir.",
        "clausules": ["en agonie au jardin des oliviers,", "trahi par un des disciples,", "dans sa Passion pour le Salut du monde,", "offrant sa vie pour la multitude,", "dans la nuit de la tristesse et de l'angoisse,", "qui se confie à la volonté du Père,", "qui se livre par amour pour moi,", "qui me demande de veiller et prier,", "avec moi dans les épreuves,", "en qui je mets ma foi et mon espérance,"]
    },
    {
        "id": 12, "titre": "LA FLAGELLATION", "reference": "Jean 19, 1", "type": "Douloureux",
        "passage": "Alors Pilate fit saisir Jésus pour qu'il soit flagellé.\n",
        "meditation": "Jésus, Dieu fait homme, est dessaisi de toute humanité, humilié. Même traité en esclave, il ne cesse pas d'être Dieu.\nDans sa chair broyée, il continue d'aimer et de se donner pour accomplir le Salut de tous les hommes.",
        "intentions": "pour ceux qui sont accusés à tort,\npour les chrétiens persécutés,\npour les victimes des régimes totalitaires,\npour que notre cœur s'ouvre aux détresses des personnes que nous côtoyons,\nIntention du prochain dans la chaine de prière,",
        "fruits": "Le pardon de nos péchés,\nLa pénitence.",
        "clausules": ["flagellé,", "Parole qui se tait,", "mis au rang des accusés,", "victime de la haine des hommes,", "qui se fait serviteur,", "accablé par le mal,", "livré aux mains des méchants,", "condamné injustement,", "qui m'aime et me pardonne,", "qui m'apprend le don total,"]
    },
    {
        "id": 13, "titre": "LE COURONNEMENT D'ÉPINES", "reference": "Marc 15, 16 - 19", "type": "Douloureux",
        "passage": "Les soldats emmenèrent Jésus à l'intérieur du palais, c'est-à-dire dans le Prétoire. Alors ils rassemblent toute la garde, ils le revêtent de pourpre, et lui posent sur la tête une couronne d'épines qu'ils ont tressée. Puis ils se mirent à lui faire des salutations, en disant: «Salut, roi des Juifs!»\nIls lui frappaient la tête avec un roseau, crachaient sur lui, et s'agenouillaient pour lui rendre hommage.\n",
        "meditation": "Jésus, mis à nu, travesti en roi dérisoire et livré aux moqueries des soldats, demeure le Souverain de l'univers.\nA ce moment même, il réalise la libération de l'humanité pour l'entraîner avec lui dans son Royaume.",
        "intentions": "pour les victimes de la dérision et de l'insulte,\npour ceux qui subissent des condamnations arbitraires,\npour ceux qui supportent l'humiliation et le mépris,\npour que notre cœur apprenne la compassion,\nIntention du prochain dans la chaine de prière,",
        "fruits": "L'humilité,\nLe courage.",
        "clausules": ["couronné d'épines,", "livré à la moquerie,", "humilié par les soldats,", "qui supporte en silence ses souffrances,", "dont le règne n'est pas de ce monde,", "serviteur souffrant et humble,", "agneau muet conduit à l'abattoir,", "auprès de moi quand je souffre,", "qui m'apprend le courage dans les épreuves,", "mon Roi et mon Dieu,"]
    },
    {
        "id": 14, "titre": "LE PORTEMENT DE CROIX", "reference": "Marc 15, 20 - 23", "type": "Douloureux",
        "passage": "Ils emmènent Jésus pour le crucifier, et ils réquisitionnent, pour porter sa croix, un passant, Simon de Cyrène, le père d'Alexandre et de Rufus, qui revenait des champs.\nEt ils amènent Jésus au lieu dit Golgotha, ce qui se traduit: Lieu-du-Crâne (ou Calvaire).\nIls lui donnent du vin aromatisé de myrrhe; mais il n'en prit pas.\n",
        "meditation": "Jésus supporte, en même temps que sa croix, la souffrance et le péché de toute l'humanité. Ceux qui le suivent dans le don d'eux-mêmes sans reserve portent avec lui le monde.",
        "intentions": "pour ceux qui sont accablés par la vie,\npour ceux qui se dévouent généreusement auprès des souffrants,\npour que nous venions en aide à ceux qui portent une croix trop lourde,\npour que notre cœur de pierre se transforme en cœur de chair,\nIntention du prochain dans la chaine de prière,",
        "fruits": "L'acceptation de nos peines,\nLa patience dans les épreuves.",
        "clausules": ["chargé de la croix,", "aidé de Simon de Cyrène,", "qui porte le péché du monde,", "qui porte nos souffrances,", "qui rachète les multitudes,", "confondu avec les malfaiteurs,", "qui aime l'humanité jusqu'au bout,", "qui souffre dans son Corps,", "sans éclat ni beauté,", "qui m'épaule pour porter ma croix,"]
    },
    {
        "id": 15, "titre": "LA MORT DE JÉSUS SUR LA CROIX", "reference": "Luc 23, 33 - 34; 44 - 47", "type": "Douloureux",
        "passage": "Lorsqu'ils furent arrivés au lieu dit: Le Crâne (ou Calvaire), là ils crucifièrent Jésus, avec les malfaiteurs, l'un à droite et l'autre à gauche.\nJésus disait: «Père, pardonne-leur: ils ne savent ce qu'ils font.» Puis, ils partagèrent ses vêtements et les tirèrent au sort.\nC'était déjà environ la sixième heure (c'est-à-dire midi); l'obscurité se fit sur la terre jusqu'à la neuvième heure, car le soleil s'était caché.\nLe rideau du Sanctuaire se déchira par le milieu. Alors Jésus poussa un grand cri: «Père, entre tes mains je remets mon esprit.» Et après avoir dit cela, il expira.\nA la vue de ce qui s'était passé, le centurion rendit gloire à Dieu: «Celui-ci était réellement un homme juste!»\n",
        "meditation": "Jésus, le Fils de Dieu, consent à mourir comme un malfaiteur, confondu avec les pécheurs. C'est notre péché qui est cloué avec Lui et c'est notre mort qui meurt avec Lui.",
        "intentions": "pour ceux qui sont à l'heure de la mort,\npour ceux qui ont perdu un être aimé,\npour l'Église née du coté transpercé du Christ,\npour que notre cœur s'ouvre à la miséricorde,\nIntention du prochain dans la chaine de prière,",
        "fruits": "La persévérance,\nLa foi dans le Salut.",
        "clausules": ["qui pardonne à ses bourreaux,", "miséricordieux qui ouvre le paradis au larron,", "abandonné de tous,", "immolé sur la croix,", "aimant les siens jusqu'à la fin,", "obéissant jusqu'à la mort,", "qui remet son Esprit au Père,", "qui attire à Lui tous les hommes,", "qui arrache ma vie à la mort,", "qui m'apprend à donner ma vie,"]
    },
    {
        "id": 16, "titre": "LA RÉSURRECTION", "reference": "Matthieu 28, 5 - 7", "type": "Glorieux",
        "passage": "L'ange prit la parole et dit aux femmes: «Vous, soyez sans crainte! Je sais bien que vous cherchez Jésus le Crucifié. Il n'est pas ici, car il est ressuscité, comme il l'avait dit. Venez voir l'endroit où il reposait.\nPuis, vite, allez dire à ses disciples: \"Il est ressuscité d'entre les morts, et voici qu'il vous précède en Galilée; là, vous le verrez.\"Voilà ce que j'avais à vous dire.»\n",
        "meditation": "Le corps de Jésus, meurtri, torturé, descendu de la croix le vendredi soir, veille du sabbat, n'a pu être embaumé selon les coutumes.\nDe grand matin, les femmes viennent au tombeau pour accomplir ces gestes rituels.\nLe tombeau est ouvert. Le corps n'est plus là. Le Christ a vaincu la mort!\nLa mort n'a pu retenir dans ses liens Celui qui est la vie!",
        "intentions": "pour le pape, les évêques chargés de veiller sur la foi catholique reçue des Apôtres,\npour que la joie de la Résurrection illumine toute notre vie,\npour ceux qui sont en recherche de la vérité,\npour les incroyants,\nIntention du prochain dans la chaine de prière,",
        "fruits": "La Foi.",
        "clausules": ["qui a vaincu la mort,", "ressuscité selon les Écritures,", "qui apparait à Marie-Madeleine,", "qui apparait aux Apôtres,", "qui chemine avec les disciples d'Emmaüs,", "qui montre ses plaies à Thomas,", "notre vie et notre résurrection,", "qui se révèle à ceux qui le cherchent,", "qui chemine avec nous sur la route,", "qui nous donne sa Paix,"]
    },
    {
        "id": 17, "titre": "L'ASCENSION", "reference": "Marc 16, 19 - 20", "type": "Glorieux",
        "passage": "Le Seigneur Jésus, après avoir parlé à ses disciples, fut enlevé au ciel et il s'assit à la droite de Dieu.\nQuant à eux, ils s'en allèrent proclamer partout l'Évangile. Le Seigneur travaillait avec eux et confirmait la Parole par les signes qui l'accompagnaient.\n",
        "meditation": "Quarante jours après la Pâques, le Christ ressuscité remonte vers le Père avec toute son humanité.\nA sa suite, toute l'humanité est appelée à siéger à la droite du Père et à participer à sa divinité.",
        "intentions": "pour que nous recherchions les réalités d'En-Haut, là où se trouve le Christ,\npour que nous ayons confiance et une ferme espérance dans les promesses de Jésus,\npour que notre cœur ne s'attache pas aux choses périssables,\nIntention du prochain dans la chaine de prière,",
        "fruits": "L'espérance.",
        "clausules": ["qui bénit ses disciples avant de les quitter,", "qui promet l'Esprit Saint,", "qui remplit de joie le cœur des Apôtres,", "qui monte vers son Père et Notre Père,", "qui règne à la droite du Père,", "qui ne nous laisse pas orphelins,", "qui intercède pour nous auprès du Père,", "qui demeure pour toujours avec nous,", "qui nous attire vers le Ciel,", "qui nous appelle à faire des disciples de toutes les nations,"]
    },
    {
        "id": 18, "titre": "LA PENTECÔTE", "reference": "Actes des Apôtres 1, 13 - 14; 2, 2 - 4", "type": "Glorieux",
        "passage": "A leur arrivée en ville, les Apôtres montèrent dans la chambre haute où ils se tenaient habituellement. [...] Tous d'un même cœur, étaient assidus à la prière, avec des femmes, avec Marie la mère de Jésus, et avec ses frères. [...]\nLe jour de la Pentecôte étant arrivé, un bruit survint du ciel comme un violent coup de vent: la maison où ils étaient en fut remplie toute entière. Alors apparurent des langues qu'on aurait dites de feu, qui se partageaient, et il s'en posa une sur chacun d'eux.\n\nTous furent remplis d'Esprit Saint: ils se mirent à parler en d'autres langues, et chacun s'exprimait selon le don de l'Esprit.\n",
        "meditation": "Dans les derniers jours, dit Dieu, je répandrai mon Esprit sur toute chair. La prophétie de Joël se réalise.\nJésus glorifié par le Père accomplit les Écritures et réalise les promesses de Dieu.\nPar l'Esprit Saint, Dieu se communique et se fait connaître.",
        "intentions": "pour que nous soyons dociles au souffle de l'Esprit,\npour que nous soyons assidus à la prière et à l'écoute de la Parole de Dieu,\npour que nous témoignons du Christ par toute notre vie,\nIntention du prochain dans la chaine de prière,",
        "fruits": "La Charité,\nL'effusion de l'Esprit,\nUne âme d'apôtre.",
        "clausules": ["qui envoie l'Esprit Saint que le Père avait promis,", "dont l'Esprit descend sur les Apôtres comme des langues de feu,", "dont l'Esprit rassemble tous les hommes,", "dont l'Esprit se répand dans les cœurs,", "dont l'Esprit maintient l'Église dans la Vérité,", "dont l'Esprit est à l'œuvre en tout homme qui aime,", "dont l'Esprit diffuse l'amour dans les cœurs,", "dont l'Esprit inspire toute prière,", "qui nous veut assidus à la prière,", "dont l'Esprit nous entraine à proclamer la Résurrection,"]
    },
    {
        "id": 19, "titre": "L'ASSOMPTION", "reference": "Jean 17, 24", "type": "Glorieux",
        "passage": "Jésus dit: «Père, ceux que tu m'as donnés, je veux que là où je suis, ils soient eux aussi avec moi, et qu'ils contemplent ma gloire, celle que tu m'as donnée.»\n",
        "meditation": "Au terme de sa vie terrestre, par une grâce spéciale venant de la résurrection de son Fils, la Vierge Marie est élevée dans la gloire du Ciel.\nImage de l'Église à venir, elle anticipe la résurrection de tous les membres du Corps du Christ.",
        "intentions": "pour que nous partagions ta joie et l'exultation de ta louange,\npour que nous entrions dans ton cantique d'action de grâce,\npour que les défunts qui nous sont chers accèdent au Royaume,\nIntention du prochain dans la chaine de prière,",
        "fruits": "La grâce d'une mort dans la Foi et l'Espérance.",
        "clausules": ["qui a préservé votre corps de la corruption du tombeau,", "dont l'Esprit transfigure votre corps et votre Esprit,", "qui vous élève corps et âme dans sa Gloire,", "qui vous élève au-dessus des anges,", "qui inaugure en vous ce qu'Il accomplira pour toute l'Église,", "qui fait de vous l'image parfaite de l'Église,", "qui a remis l'Église sous votre maternelle protection,", "qui tourne nos désirs vers les réalités éternelles,", "qui transfigurera nos corps de misère en son Corps de gloire,", "qui nous ressuscitera à la fin des temps,"]
    },
    {
        "id": 20, "titre": "LE COURONNEMENT DE MARIE", "reference": "Apocalypse 12, 1", "type": "Glorieux",
        "passage": "Un grand signe apparut dans le ciel: une Femme, ayant le soleil pour manteau, la lune sous ses pieds, et sur la tête une couronne de douze étoiles.\n",
        "meditation": "En couronnant Marie, Dieu couronne ses vertus mais surtout il couronne son humilité.\nCelle qui s'est déclarée servante du Seigneur à l'Annonciation est restée, durant toute sa vie terrestre, fidèle à ce que ce nom exprime, se confirmant ainsi véritable disciple du Christ, venu non pour être servi, mais pour servir et donner sa vie.\nC'est pourquoi Marie est devenue la première de ceux qui, servant le Christ également dans les autres, a pleinement atteint cet état de liberté royale qui est propre aux disciples du Christ: Servir, ce qui veut dire régner!\nJean Paul II, Redemptoris Mater",
        "intentions": "pour qu'adviennent le Règne du Christ, l'amour, la justice et la paix,\npour que nous en soyons les acteurs et les témoins là où nous sommes,\npour ceux qui travaillent au Royaume de Dieu,\npour que nous soyons de fidèles disciples de Jésus,\nIntention du prochain dans la chaine de prière,",
        "fruits": "L'Esprit des Béatitudes,\nLa confiance dans l'intercession de Marie.",
        "clausules": ["qui vous place auprès de Lui,", "qui fait de vous notre Mère et notre Reine,", "qui élève les humbles,", "qui fait de vous la Reine du Ciel,", "qui fait de vous la Reine de l'Église,", "qui fait de vous la Reine des Apôtres,", "qui fait de vous la Reine des Martyrs,", "qui fait de vous la Reine des tous les Saints,", "qui fait de vous la Consolatrice des Affligés,", "qui fait de vous la Médiatrice de toutes grâces,"]
    },
]


def _normalise(v):
    while v > 20:
        v -= 20
    while v <= 0:
        v += 20
    return v


def _est_bissextile(annee):
    if annee % 4 != 0:
        return False
    if annee % 100 != 0:
        return True
    return annee % 400 == 0


def _calcul_pair_standard(jour, num):
    # Fidèle au VBA : mois pairs, jours standards
    r = jour + num + (9 - 20)
    if r < 21:
        if num < 11:
            r = jour + num + (9 - 20)
            if r <= 0:
                r = jour + num + 9
        else:
            r = jour + num + (9 - 20)
            if r <= 0:
                r = jour + num + 9
    else:
        r = jour + num + (9 - 40)
        if r <= 0:
            r = jour + num + (9 - 20)
    return r


def _calcul_pair_31(num):
    # Fidèle au VBA : mois pairs, jour 31 (ex : 31 août)
    r = 30 + num + (9 - 20)
    if r < 21:
        pass
    else:
        r = 30 + num + (9 - 40)
        if r <= 0:
            r = 30 + num + (9 - 20)
    return r


def _calcul_impair_standard(jour, num):
    # Fidèle au VBA : mois impairs, jours standards
    r = jour + num + (9 - 10)
    if r < 21:
        if num < 11:
            r = jour + num + (9 - 10)
            if r <= 0:
                r = jour + num + (9 - 20)
        else:
            r = jour + num + (9 - 10)
            if r <= 0:
                r = jour + num + (9 - 20)
    else:
        r = jour + num + (9 - 30)
        if r <= 0:
            r = jour + num + (9 - 10)
    return r


def _calcul_impair_31(num):
    # Fidèle au VBA : mois impairs, jour 31
    r = 30 + num + (9 - 30)
    if r < 21:
        if num < 11:
            r = 30 + num + (9 - 30)
            if r <= 0:
                r = 30 + num + (9 - 20)
        else:
            r = 30 + num + (9 - 50)
            if r <= 0:
                r = 30 + num + (9 - 30)
    else:
        if num < 11:
            r = 30 + num + (9 - 30)
            if r <= 0:
                r = 30 + num + (9 - 20)
        else:
            r = 30 + num + (9 - 50)
            if r <= 0:
                r = 30 + num + (9 - 30)
    return r


def _calcul_fev28(num):
    # Fidèle au VBA : 28 février (fin de mois si année non bissextile)
    r = 28 + num + (9 - 20)
    if r < 21:
        pass
    else:
        r = 28 + num + (9 - 40)
        if r <= 0:
            r = 28 + num + (9 - 20)
    return r


def _calcul_fev29(num):
    # Fidèle au VBA : 29 février (année bissextile)
    r = 29 + num + (9 - 20)
    if r < 21:
        pass
    else:
        r = 29 + num + (9 - 40)
        if r <= 0:
            r = 29 + num + (9 - 20)
    return r


def calculer_mysteres_du_jour(num, date_du_jour=None):
    """Portage FIDÈLE de calculateDailyContent. Retourne la liste des ids de
    mystères (1 à 3 selon le cas spécial) pour un numéro de membre (1-20)."""
    if num <= 0 or num > 20:
        return []

    from datetime import date as _date
    d = date_du_jour or _date.today()
    jour, mois, annee = d.day, d.month, d.year

    # Dernier jour de février : si on est le 28, on regarde si l'année est bissextile
    der_jr_fev = 29 if (mois == 2 and jour == 28 and _est_bissextile(annee)) else 28

    indices = []

    if mois % 2 == 0:  # === MOIS PAIRS ===
        if mois == 2:
            if jour == 28:
                if der_jr_fev == 28:  # 28 février ET fin de mois (non bissextile) → 3 mystères
                    f6 = _calcul_fev28(num)
                    indices.append(_normalise(f6))
                    g6 = f6 + 1 if f6 < 20 else 1
                    indices.append(_normalise(g6))
                    h6 = g6 + 1 if g6 < 20 else 1
                    indices.append(_normalise(h6))
                else:  # 28 février mais ce n'est pas la fin (bissextile) → 1 mystère
                    indices.append(_normalise(_calcul_fev28(num)))
            elif jour == 29:  # 29 février (bissextile) → 2 mystères
                f6 = _calcul_fev29(num)
                indices.append(_normalise(f6))
                g6 = f6 + 1 if f6 < 20 else 1
                indices.append(_normalise(g6))
            else:  # 1er au 27 février → 1 mystère
                indices.append(_normalise(_calcul_pair_standard(jour, num)))
        else:  # autres mois pairs (avril, juin, août, octobre, décembre)
            if jour == 31:
                indices.append(_normalise(_calcul_pair_31(num)))
            else:
                indices.append(_normalise(_calcul_pair_standard(jour, num)))
    else:  # === MOIS IMPAIRS ===
        if jour == 31:
            indices.append(_normalise(_calcul_impair_31(num)))
        else:
            indices.append(_normalise(_calcul_impair_standard(jour, num)))

    return indices


def get_mystere(id_mystere):
    return next((m for m in MYSTERES if m["id"] == id_mystere), None)


def get_mysteres_du_jour(num):
    """API principale : retourne la liste des dict mystères du jour pour ce numéro."""
    ids = calculer_mysteres_du_jour(num)
    return [get_mystere(i) for i in ids if get_mystere(i) is not None]


def get_theme_actif():
    """Retourne (texte_theme, mystere_principal, annee_debut) du thème actif, ou None."""
    try:
        r = c.execute("""SELECT texte_theme, mystere_principal, annee_debut FROM themes_pastoraux
                         WHERE actif=1 ORDER BY annee_debut DESC LIMIT 1""").fetchone()
        return r
    except Exception:
        return None


def get_sous_theme_du_mois(annee_debut, mois):
    """Retourne (titre, contenu, feuillet_pdf) du sous-thème du mois, ou None."""
    try:
        return c.execute("""SELECT titre, contenu, feuillet_pdf FROM sous_themes
                            WHERE annee_debut=? AND mois=?""", (annee_debut, mois)).fetchone()
    except Exception:
        return None


def get_lien_mystere(annee_debut, mystere_id):
    """Retourne le texte du lien thématique d'un mystère pour l'année, ou None."""
    try:
        r = c.execute("""SELECT texte_lien FROM theme_mystere
                         WHERE annee_debut=? AND mystere_id=?""", (annee_debut, mystere_id)).fetchone()
        return r[0] if r else None
    except Exception:
        return None
