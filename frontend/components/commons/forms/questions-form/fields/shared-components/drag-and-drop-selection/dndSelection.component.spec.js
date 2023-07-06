import { shallowMount } from "@vue/test-utils";
import DndSelectionComponent from "./DndSelection.component";
import { adaptQuestionsToSlots } from "../../ranking/ranking-adapter";
import { settingsFake } from "../../ranking/ranking-fakes";

let wrapper = null;
const options = {
  stubs: ["draggable"],
  propsData: { ranking: {} },
};

beforeEach(() => {
  wrapper = shallowMount(DndSelectionComponent, options);
});

afterEach(() => {
  wrapper.destroy();
});

describe("DndSelectionComponent", () => {
  it("render the component", () => {
    expect(wrapper.is(DndSelectionComponent)).toBe(true);
  });
  it("has a ranking prop as required and must be an Object", () => {
    expect(DndSelectionComponent.props.ranking).toMatchObject({
      type: Object,
      required: true,
    });
  });
});

describe("rankWithKeyboard should", () => {
  it("no move question because the user press non existing slot for a key", () => {
    const ranking = adaptQuestionsToSlots(settingsFake);
    const questionOne = ranking.questions[0];
    const component = shallowMount(DndSelectionComponent, {
      ...options,
      propsData: { ranking },
    });

    component.vm.rankWithKeyboard({ key: "5" }, questionOne);

    expect(component.vm.ranking.slots[0].items.length).toBeFalsy();
    expect(component.vm.ranking.slots[1].items.length).toBeFalsy();
    expect(component.vm.ranking.slots[2].items.length).toBeFalsy();
    expect(component.vm.ranking.slots[3].items.length).toBeFalsy();
  });

  it("no move question because the user press invalid key", () => {
    const ranking = adaptQuestionsToSlots(settingsFake);
    const questionOne = ranking.questions[0];
    const component = shallowMount(DndSelectionComponent, {
      ...options,
      propsData: { ranking },
    });

    component.vm.rankWithKeyboard({ key: "&" }, questionOne);

    expect(component.vm.ranking.slots[0].items.length).toBeFalsy();
    expect(component.vm.ranking.slots[1].items.length).toBeFalsy();
    expect(component.vm.ranking.slots[2].items.length).toBeFalsy();
    expect(component.vm.ranking.slots[3].items.length).toBeFalsy();
  });

  it("move correctly question when user press 1", () => {
    const ranking = adaptQuestionsToSlots(settingsFake);
    const questionOne = ranking.questions[0];
    const component = shallowMount(DndSelectionComponent, {
      ...options,
      propsData: { ranking },
    });

    component.vm.rankWithKeyboard({ key: "1" }, questionOne);

    expect(component.vm.ranking.slots[0].items[0]).toBe(questionOne);
  });

  it("prevent duplicate question if user try to move twice the same question", () => {
    const ranking = adaptQuestionsToSlots(settingsFake);
    const questionOne = ranking.questions[0];
    const component = shallowMount(DndSelectionComponent, {
      ...options,
      propsData: { ranking },
    });
    component.vm.rankWithKeyboard({ key: "1" }, questionOne);

    component.vm.rankWithKeyboard({ key: "1" }, questionOne);

    expect(component.vm.ranking.slots[0].items[0]).toBe(questionOne);
    expect(component.vm.ranking.slots[0].items.length).toBe(1);
    expect(component.vm.ranking.questions.length).toBe(3);
  });

  it("prevent duplicate question if user try to move twice the same question", () => {
    const ranking = adaptQuestionsToSlots(settingsFake);
    const questionOne = ranking.questions[0];
    const component = shallowMount(DndSelectionComponent, {
      ...options,
      propsData: { ranking },
    });
    component.vm.rankWithKeyboard({ key: "1" }, questionOne);

    component.vm.rankWithKeyboard({ key: "1" }, questionOne);

    expect(component.vm.ranking.slots[0].items[0]).toBe(questionOne);
    expect(component.vm.ranking.slots[0].items.length).toBe(1);
    expect(component.vm.ranking.questions.length).toBe(3);
  });

  it("move a question from any slot to other one", () => {
    const ranking = adaptQuestionsToSlots(settingsFake);
    const questionOne = ranking.questions[0];
    const component = shallowMount(DndSelectionComponent, {
      ...options,
      propsData: { ranking },
    });
    component.vm.rankWithKeyboard({ key: "2" }, questionOne);

    component.vm.rankWithKeyboard({ key: "1" }, questionOne);

    expect(component.vm.ranking.slots[0].items[0]).toBe(questionOne);
    expect(component.vm.ranking.slots[0].items.length).toBe(1);
    expect(component.vm.ranking.questions.length).toBe(3);
    expect(component.vm.ranking.slots[1].items.length).toBe(0);
  });
});
